"""
Turkish Singer Guess - Web App
Run with: python app.py
Then open: http://localhost:5000
"""

from flask import Flask, render_template, jsonify, request, session, send_from_directory, send_file, redirect
import json
import os
from datetime import datetime, timedelta
from functools import wraps
import pytz

app = Flask(__name__)
app.secret_key = 'turkish-singer-guess-secret-key-change-in-production'

# ============================================================
# Data Loading
# ============================================================

ARTISTS = []
ARTISTS_BY_ID = {}
ARTISTS_BY_NAME = {}

def load_artists():
    global ARTISTS, ARTISTS_BY_ID, ARTISTS_BY_NAME
    
    # Resolve paths relative to this file so they work regardless of current working directory
    base = os.path.dirname(os.path.abspath(__file__))
    # Prefer DataCollection/output (source of truth) so the game always uses the updated JSON
    data_collection_path = os.path.abspath(os.path.join(base, '..', 'DataCollection', 'output', 'artists_raw.json'))
    webapp_data_path = os.path.abspath(os.path.join(base, 'data', 'artists_raw.json'))
    if os.path.isfile(data_collection_path):
        filepath = data_collection_path
    elif os.path.isfile(webapp_data_path):
        filepath = webapp_data_path
    else:
        raise FileNotFoundError(
            f"Artist data not found. Put artists_raw.json in DataCollection/output/ or WebApp/data/. "
            f"Tried: {data_collection_path!r} and {webapp_data_path!r}"
        )
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        raw_artists = json.load(f)
    load_artists._loaded_from = filepath
    
    ARTISTS = []
    for raw in raw_artists:
        genres_list = raw.get('genres') or []
        artist = {
            'id': raw['id'],
            'name': raw['name'],
            'nationality': raw.get('nationality'),
            'popularity': raw.get('popularity', 0),
            'debut_year': raw.get('debut'),
            'group_size': raw.get('group_size'),
            'gender': raw.get('gender'),
            'genre': genres_list[0] if genres_list else None,
            'genres': genres_list,
            'image_url': raw.get('image_url'),
            'top_track_id': raw.get('top_track_id'),
            'top_track_name': raw.get('top_track_name'),
            'top_track_uri': raw.get('top_track_uri'),
        }
        ARTISTS.append(artist)
    
    ARTISTS_BY_ID = {a['id']: a for a in ARTISTS}
    ARTISTS_BY_NAME = {a['name'].lower(): a for a in ARTISTS}


def _raw_artist_from_file(artist_id):
    """Return the raw artist dict from the JSON file for this id, or None."""
    filepath = getattr(load_artists, '_loaded_from', None)
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            raw_list = json.load(f)
    except Exception:
        return None
    for raw in raw_list:
        if raw.get('id') == artist_id:
            return raw
    return None


def artist_for_api(a):
    """Return artist dict with all fields the client needs (debut_year, genres, etc.)."""
    if not a:
        return {}
    # Support both 'debut_year' (our in-memory key) and 'debut' (raw JSON key)
    debut = a.get('debut_year') if a.get('debut_year') is not None else a.get('debut')
    genres = a.get('genres')
    if genres is None:
        genres = []
    return {
        'id': a.get('id'),
        'name': a.get('name'),
        'nationality': a.get('nationality'),
        'popularity': a.get('popularity', 0),
        'debut_year': debut,
        'group_size': a.get('group_size'),
        'gender': a.get('gender'),
        'genre': a.get('genre'),
        'genres': genres,
        'image_url': a.get('image_url'),
        'top_track_id': a.get('top_track_id'),
        'top_track_name': a.get('top_track_name'),
        'top_track_uri': a.get('top_track_uri'),
    }

# ============================================================
# Daily Artist Selection (Deterministic - Turkey Timezone)
# ============================================================

TURKEY_TZ = pytz.timezone('Europe/Istanbul')
EPOCH_DATE = datetime(2025, 1, 1)

def get_turkey_now():
    """Get current time in Turkey timezone (UTC+3)"""
    return datetime.now(TURKEY_TZ)

def get_daily_artist():
    if not ARTISTS:
        return None
    days_since_epoch = (get_turkey_now().date() - EPOCH_DATE.date()).days
    seed = abs(days_since_epoch)
    hash_val = (seed * 6364136223846793005 + 1442695040888963407) % (2**64)
    index = hash_val % len(ARTISTS)
    return ARTISTS[index]

def get_date_string():
    return get_turkey_now().strftime('%Y-%m-%d')

# ============================================================
# Search
# ============================================================

def search_artists(query, limit=8):
    query = query.strip().lower()
    if not query:
        return []
    
    results = [a for a in ARTISTS if query in a['name'].lower()]
    
    def sort_key(a):
        name = a['name'].lower()
        if name == query:
            return (0, a['popularity'])
        if name.startswith(query):
            return (1, a['popularity'])
        return (2, a['popularity'])
    
    results.sort(key=sort_key)
    return results[:limit]

# ============================================================
# Hint Engine
# ============================================================

def compare_artists(guessed, correct):
    if guessed['id'] == correct['id']:
        return {
            'debut_year': {'result': 'correct'},
            'group_size': {'result': 'correct'},
            'gender': {'result': 'correct'},
            'genre': {'result': 'correct'},
            'nationality': {'result': 'correct'},
            'popularity': {'result': 'correct'},
        }
    
    return {
        'debut_year': compare_numeric(guessed.get('debut_year'), correct.get('debut_year'), 10, False),
        'group_size': compare_exact(guessed.get('group_size'), correct.get('group_size')),
        'gender': compare_exact(guessed.get('gender'), correct.get('gender')),
        'genre': compare_genres(guessed.get('genres'), correct.get('genres')),
        'nationality': compare_exact_ci(guessed.get('nationality'), correct.get('nationality')),
        # Popularity = rank (1 = most streams). Lower number = more popular. "Close" = within 15 ranks.
        'popularity': compare_popularity(guessed.get('popularity'), correct.get('popularity'), 15),
    }

def compare_numeric(guessed, correct, threshold, is_percentage):
    if guessed is None or correct is None:
        return {'result': 'unknown'}
    
    try:
        guessed_num = int(guessed) if isinstance(guessed, str) else guessed
        correct_num = int(correct) if isinstance(correct, str) else correct
    except (ValueError, TypeError):
        return {'result': 'unknown'}
    
    if guessed_num == correct_num:
        return {'result': 'correct'}
    
    if is_percentage:
        diff = abs(guessed_num - correct_num) / max(correct_num, 1)
    else:
        diff = abs(guessed_num - correct_num)
    
    is_close = diff <= threshold
    direction = 'higher' if correct_num > guessed_num else 'lower'
    
    if is_close:
        return {'result': 'close', 'direction': direction}
    return {'result': direction}


def compare_popularity(guessed, correct, close_ranks):
    """Popularity is rank: 1 = most streams (best), higher number = less popular. Close = within close_ranks."""
    if guessed is None or correct is None:
        return {'result': 'unknown'}
    try:
        guessed_num = int(guessed) if isinstance(guessed, str) else guessed
        correct_num = int(correct) if isinstance(correct, str) else correct
    except (ValueError, TypeError):
        return {'result': 'unknown'}
    if guessed_num == correct_num:
        return {'result': 'correct'}
    diff = abs(guessed_num - correct_num)
    is_close = diff <= close_ranks
    # "higher" = correct is more popular = correct has lower rank number
    direction = 'higher' if correct_num < guessed_num else 'lower'
    if is_close:
        return {'result': 'close', 'direction': direction}
    return {'result': direction}

def compare_exact(guessed, correct):
    if guessed is None or correct is None:
        return {'result': 'unknown'}
    return {'result': 'correct' if guessed == correct else 'incorrect'}

def compare_exact_ci(guessed, correct):
    if guessed is None or correct is None:
        return {'result': 'unknown'}
    return {'result': 'correct' if guessed.lower() == correct.lower() else 'incorrect'}


def compare_genres(guessed_genres, correct_genres):
    """Compare genre lists: correct = exact match (same set), close = at least one genre in common."""
    guessed_set = {g.strip().lower() for g in (guessed_genres or []) if g and str(g).strip()}
    correct_set = {g.strip().lower() for g in (correct_genres or []) if g and str(g).strip()}
    if not correct_set and not guessed_set:
        return {'result': 'unknown'}
    if not correct_set or not guessed_set:
        return {'result': 'incorrect'}
    if guessed_set == correct_set:
        return {'result': 'correct'}
    if guessed_set & correct_set:
        return {'result': 'close'}
    return {'result': 'incorrect'}

# ============================================================
# Game State Management
# ============================================================

def get_game_state():
    today = get_date_string()
    # Custom puzzle link: do not overwrite session
    if session.get('is_custom_puzzle'):
        return {
            'date': session.get('game_date', 'custom'),
            'guesses': session.get('guesses', []),
            'status': session.get('status', 'playing'),
            'remaining': 10 - len(session.get('guesses', []))
        }
    if 'game_date' not in session or session['game_date'] != today:
        # New day, new game
        correct_artist = get_daily_artist()
        session['game_date'] = today
        session['correct_artist_id'] = correct_artist['id']
        session['guesses'] = []
        session['status'] = 'playing'
    guesses = []
    for g in session.get('guesses', []):
        full_artist = ARTISTS_BY_ID.get(g.get('artist_id')) if g.get('artist_id') else None
        guess_copy = dict(g)
        artist_payload = artist_for_api(full_artist) if full_artist else (g.get('artist') or {})
        if not artist_payload.get('debut_year'):
            raw = _raw_artist_from_file(g.get('artist_id')) if g.get('artist_id') else None
            if raw:
                artist_payload['debut_year'] = raw.get('debut') or raw.get('Debut')
        guess_copy['artist'] = artist_payload
        guesses.append(guess_copy)
    return {
        'date': session['game_date'],
        'guesses': guesses,
        'status': session['status'],
        'remaining': 10 - len(session['guesses'])
    }

def make_guess(artist_id):
    if session.get('status') != 'playing':
        return {'error': 'Game is over'}
    
    if len(session.get('guesses', [])) >= 10:
        return {'error': 'No more guesses'}
    
    if any(g['artist_id'] == artist_id for g in session.get('guesses', [])):
        return {'error': 'Already guessed'}
    
    guessed = ARTISTS_BY_ID.get(artist_id)
    correct = ARTISTS_BY_ID.get(session['correct_artist_id'])
    
    if not guessed:
        return {'error': 'Artist not found'}
    
    hints = compare_artists(guessed, correct)
    is_correct = guessed['id'] == correct['id']
    
    # Ensure debut_year is set from file when missing (fixes display when in-memory copy lacks it)
    if not guessed.get('debut_year'):
        raw = _raw_artist_from_file(artist_id)
        if raw and (raw.get('debut') or raw.get('Debut')):
            guessed['debut_year'] = raw.get('debut') or raw.get('Debut')
    
    artist_payload = artist_for_api(guessed)
    guess_record = {
        'artist_id': artist_id,
        'artist': artist_payload,
        'hints': hints,
        'is_correct': is_correct
    }
    
    session['guesses'] = session.get('guesses', []) + [guess_record]
    
    if is_correct:
        session['status'] = 'won'
    elif len(session['guesses']) >= 10:
        session['status'] = 'lost'
    
    session.modified = True
    
    return {
        'guess': guess_record,
        'status': session['status'],
        'remaining': 10 - len(session['guesses'])
    }

# ============================================================
# Paths to sibling project (for local dev: hub + SportsGuesser)
# ============================================================

WEBAPP_ROOT = os.path.dirname(os.path.abspath(__file__))
# Cursor_Projects root (parent of Trackzy) so we can reach sibling SportsGuesser
PROJECTS_ROOT = os.path.dirname(os.path.dirname(WEBAPP_ROOT))  # .../Trackzy -> .../Cursor_Projects
SPORTSGUESSER_WEB = os.path.join(PROJECTS_ROOT, 'SportsGuesser', 'web')
SPORTSGUESSER_ALLPLAYERS = os.path.join(PROJECTS_ROOT, 'SportsGuesser', 'DataCollection', 'output', 'allplayers.json')

def sportsguesser_available():
    return os.path.isdir(SPORTSGUESSER_WEB)

# ============================================================
# Routes
# ============================================================

@app.route('/')
def home():
    """Hub: pick a game (Trackzy, SportsGuesser, etc.)."""
    return render_template('home.html', sportsguesser_available=sportsguesser_available())


@app.route('/trackzy')
def trackzy():
    """Trackzy game: Turkish singer guess."""
    artist_id = request.args.get('artist', '').strip()
    if artist_id and artist_id in ARTISTS_BY_ID:
        session['is_custom_puzzle'] = True
        session['game_date'] = 'custom'
        session['correct_artist_id'] = artist_id
        session['guesses'] = []
        session['status'] = 'playing'
        session.modified = True
    else:
        if session.get('is_custom_puzzle'):
            session.pop('is_custom_puzzle', None)
        correct_artist = get_daily_artist()
        session['game_date'] = get_date_string()
        session['correct_artist_id'] = correct_artist['id']
        session['guesses'] = []
        session['status'] = 'playing'
        session.modified = True
    return render_template('trackzy.html')

@app.route('/api/state')
def api_state():
    state = get_game_state()
    return jsonify(state)

@app.route('/api/genres')
def api_genres():
    """Return sorted list of all unique genres in the dataset (for reference)."""
    genres = set()
    for a in ARTISTS:
        for g in (a.get('genres') or []):
            if g and str(g).strip():
                genres.add(str(g).strip())
    return jsonify(sorted(genres))

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    results = search_artists(query)
    # Don't send full artist data, just what's needed for search
    return jsonify([{
        'id': a['id'],
        'name': a['name'],
        'nationality': a.get('nationality'),
        'image_url': a.get('image_url'),
    } for a in results])

@app.route('/api/guess', methods=['POST'])
def api_guess():
    data = request.get_json()
    artist_id = data.get('artist_id')
    result = make_guess(artist_id)
    return jsonify(result)

@app.route('/api/answer')
def api_answer():
    """Only available after game is over"""
    if session.get('status') not in ['won', 'lost']:
        return jsonify({'error': 'Game still in progress'}), 403
    
    correct = ARTISTS_BY_ID.get(session['correct_artist_id'])
    return jsonify(correct)

@app.route('/api/debug/answer')
def api_debug_answer():
    """Debug endpoint - shows answer (for testing only)"""
    correct = ARTISTS_BY_ID.get(session.get('correct_artist_id'))
    if not correct:
        correct = get_daily_artist()
    return jsonify(correct)

@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Reset game state for testing"""
    session.clear()
    return jsonify({'message': 'Game reset', 'status': 'ok'})

@app.route('/api/debug/artist/<artist_id>')
def api_debug_artist(artist_id):
    """Debug endpoint - shows artist data"""
    artist = ARTISTS_BY_ID.get(artist_id)
    return jsonify(artist if artist else {'error': 'Not found'})

@app.route('/api/next-reset')
def api_next_reset():
    """Returns seconds until midnight Turkey time (next artist reset)"""
    now = get_turkey_now()
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now.hour != 0 or now.minute != 0 or now.second != 0:
        tomorrow = tomorrow + timedelta(days=1)
    seconds_remaining = (tomorrow - now).total_seconds()
    return jsonify({
        'seconds_remaining': int(seconds_remaining),
        'turkey_time': now.strftime('%H:%M:%S'),
        'reset_at': '00:00 Turkey Time'
    })

# ============================================================
# SportsGuesser (served from sibling project when available)
# ============================================================

@app.route('/sportsguesser')
def sportsguesser_redirect():
    """Redirect to trailing slash so relative assets resolve under /sportsguesser/."""
    return redirect('/sportsguesser/', 302)


@app.route('/sportsguesser/')
def sportsguesser_index():
    if not sportsguesser_available():
        return render_template('home.html', sportsguesser_available=False), 404
    return send_file(os.path.join(SPORTSGUESSER_WEB, 'index.html'))


@app.route('/sportsguesser/api/allplayers')
def sportsguesser_api_allplayers():
    if not os.path.isfile(SPORTSGUESSER_ALLPLAYERS):
        return jsonify({'error': 'Data not found'}), 404
    with open(SPORTSGUESSER_ALLPLAYERS, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data)


@app.route('/sportsguesser/<path:subpath>')
def sportsguesser_static(subpath):
    if not sportsguesser_available():
        return jsonify({'error': 'Not found'}), 404
    path = os.path.join(SPORTSGUESSER_WEB, subpath)
    if not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(SPORTSGUESSER_WEB, subpath)

# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    load_artists()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    loaded_from = getattr(load_artists, '_loaded_from', 'unknown')
    print(f"\n{'='*50}")
    print("Tracksy - Web App")
    print(f"{'='*50}")
    print(f"Data file: {loaded_from}")
    print(f"Loaded {len(ARTISTS)} artists")
    print(f"Today's artist: {get_daily_artist()['name']}")
    print(f"\nOpen in browser: http://localhost:{port}")
    print("(Restart the server after updating artists_raw.json to see changes)")
    print(f"{'='*50}\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
