"""
Harman Games — Main site (hub) and game routing.
Serves: / (hub), /trackzy (Trackzy game), /sportsguesser (SportsGuesser).
Run from HarmanGames: python app.py → http://localhost:5000
"""

from flask import Flask, render_template, jsonify, request, session, send_from_directory, send_file, redirect
import json
import os
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'harman-games-secret-key-change-in-production')

# ============================================================
# Paths: HarmanGames is the main project; games are siblings
# ============================================================

HARMAN_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECTS_ROOT = os.path.dirname(HARMAN_ROOT)  # Cursor_Projects

# Trackzy (sub-content): artist data lives in Trackzy project
TRACKZY_ARTISTS = os.path.join(PROJECTS_ROOT, 'Trackzy', 'DataCollection', 'output', 'artists_raw.json')
TRACKZY_ARTISTS_LOCAL = os.path.join(HARMAN_ROOT, 'data', 'artists_raw.json')

# SportsGuesser (sub-content)
SPORTSGUESSER_WEB = os.path.join(PROJECTS_ROOT, 'SportsGuesser', 'web')
SPORTSGUESSER_ALLPLAYERS = os.path.join(PROJECTS_ROOT, 'SportsGuesser', 'DataCollection', 'output', 'allplayers.json')


def sportsguesser_available():
    return os.path.isdir(SPORTSGUESSER_WEB)

# ============================================================
# Trackzy: Data loading
# ============================================================

ARTISTS = []
ARTISTS_BY_ID = {}
ARTISTS_BY_NAME = {}
RAW_ARTISTS_BY_ID = {}

def load_artists():
    global ARTISTS, ARTISTS_BY_ID, ARTISTS_BY_NAME, RAW_ARTISTS_BY_ID
    filepath = TRACKZY_ARTISTS_LOCAL if os.path.isfile(TRACKZY_ARTISTS_LOCAL) else TRACKZY_ARTISTS
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Artist data not found. Add data/artists_raw.json or run from repo with Trackzy/DataCollection.")
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        raw_artists = json.load(f)
    ARTISTS = []
    for raw in raw_artists:
        genres_list = raw.get('genres') if isinstance(raw.get('genres'), list) else []
        artist = {
            'id': raw['id'],
            'name': raw['name'],
            'nationality': raw.get('nationality'),
            'popularity': raw.get('popularity', 0),
            'debut_year': raw.get('debut'),
            'group_size': raw.get('group_size'),
            'gender': raw.get('gender'),
            'genre': genres_list[0] if genres_list else None,
            'genres': list(genres_list),
            'image_url': raw.get('image_url'),
            'top_track_id': raw.get('top_track_id'),
            'top_track_name': raw.get('top_track_name'),
            'top_track_uri': raw.get('top_track_uri'),
        }
        ARTISTS.append(artist)
    ARTISTS_BY_ID = {a['id']: a for a in ARTISTS}
    ARTISTS_BY_NAME = {a['name'].lower(): a for a in ARTISTS}
    RAW_ARTISTS_BY_ID = {r['id']: r for r in raw_artists}


def _artist_payload_from_raw(raw):
    """Build artist dict for API from raw JSON so response always has full 'genres' array."""
    if not raw:
        return {}
    genres = raw.get('genres')
    if not isinstance(genres, list):
        genres = []
    genres = list(genres)
    return {
        'id': raw.get('id'),
        'name': raw.get('name'),
        'nationality': raw.get('nationality'),
        'popularity': raw.get('popularity', 0),
        'debut_year': raw.get('debut'),
        'group_size': raw.get('group_size'),
        'gender': raw.get('gender'),
        'genre': genres[0] if genres else None,
        'genres': genres,
        'image_url': raw.get('image_url'),
        'top_track_id': raw.get('top_track_id'),
        'top_track_name': raw.get('top_track_name'),
        'top_track_uri': raw.get('top_track_uri'),
    }


# ============================================================
# Trackzy: Daily artist, search, hints, game state
# ============================================================

TURKEY_TZ = pytz.timezone('Europe/Istanbul')
EPOCH_DATE = datetime(2025, 1, 1)

def get_turkey_now():
    return datetime.now(TURKEY_TZ)

def get_daily_artist():
    if not ARTISTS:
        return None
    days_since_epoch = (get_turkey_now().date() - EPOCH_DATE.date()).days
    seed = abs(days_since_epoch)
    hash_val = (seed * 6364136223846793005 + 1442695040888963407) % (2**64)
    return ARTISTS[hash_val % len(ARTISTS)]

def get_date_string():
    return get_turkey_now().strftime('%Y-%m-%d')

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
    diff = abs(guessed_num - correct_num)
    is_close = diff <= threshold
    direction = 'higher' if correct_num > guessed_num else 'lower'
    return {'result': 'close', 'direction': direction} if is_close else {'result': direction}

def compare_popularity(guessed, correct, close_ranks):
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
    direction = 'higher' if correct_num < guessed_num else 'lower'
    return {'result': 'close', 'direction': direction} if is_close else {'result': direction}

def compare_exact(guessed, correct):
    if guessed is None or correct is None:
        return {'result': 'unknown'}
    return {'result': 'correct' if guessed == correct else 'incorrect'}

def compare_exact_ci(guessed, correct):
    if guessed is None or correct is None:
        return {'result': 'unknown'}
    return {'result': 'correct' if guessed.lower() == correct.lower() else 'incorrect'}

def compare_artists(guessed, correct):
    if guessed['id'] == correct['id']:
        return {k: {'result': 'correct'} for k in ('debut_year', 'group_size', 'gender', 'genre', 'nationality', 'popularity')}
    return {
        'debut_year': compare_numeric(guessed.get('debut_year'), correct.get('debut_year'), 10, False),
        'group_size': compare_exact(guessed.get('group_size'), correct.get('group_size')),
        'gender': compare_exact(guessed.get('gender'), correct.get('gender')),
        'genre': compare_exact_ci(guessed.get('genre'), correct.get('genre')),
        'nationality': compare_exact_ci(guessed.get('nationality'), correct.get('nationality')),
        'popularity': compare_popularity(guessed.get('popularity'), correct.get('popularity'), 15),
    }

def get_game_state():
    today = get_date_string()
    if session.get('is_custom_puzzle'):
        return {
            'date': session.get('game_date', 'custom'),
            'guesses': session.get('guesses', []),
            'status': session.get('status', 'playing'),
            'remaining': 10 - len(session.get('guesses', []))
        }
    if 'game_date' not in session or session['game_date'] != today:
        correct_artist = get_daily_artist()
        session['game_date'] = today
        session['correct_artist_id'] = correct_artist['id']
        session['guesses'] = []
        session['status'] = 'playing'
    guesses = []
    for g in session.get('guesses', []):
        g_copy = dict(g)
        aid = g.get('artist_id')
        raw = RAW_ARTISTS_BY_ID.get(aid) if aid else None
        g_copy['artist'] = _artist_payload_from_raw(raw) if raw else g.get('artist') or ARTISTS_BY_ID.get(aid) or {}
        if 'genres' not in g_copy['artist'] or not isinstance(g_copy['artist'].get('genres'), list):
            a = ARTISTS_BY_ID.get(aid)
            g_copy['artist']['genres'] = list(a.get('genres') or []) if a else (g_copy['artist'].get('genre') and [g_copy['artist']['genre']]) or []
        guesses.append(g_copy)
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
    raw = RAW_ARTISTS_BY_ID.get(artist_id)
    artist_payload = _artist_payload_from_raw(raw) if raw else guessed
    guess_record = {'artist_id': artist_id, 'artist': artist_payload, 'hints': hints, 'is_correct': is_correct}
    session['guesses'] = session.get('guesses', []) + [guess_record]
    if is_correct:
        session['status'] = 'won'
    elif len(session['guesses']) >= 10:
        session['status'] = 'lost'
    session.modified = True
    return {'guess': guess_record, 'status': session['status'], 'remaining': 10 - len(session['guesses'])}

# ============================================================
# Routes: Hub (main page)
# ============================================================

@app.route('/')
def home():
    """Harman Games hub: pick a game (Trackzy, SportsGuesser, …)."""
    return render_template('home.html', sportsguesser_available=sportsguesser_available())

# ============================================================
# Routes: Trackzy (sub-content)
# ============================================================

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
    return jsonify(get_game_state())

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    results = search_artists(query)
    return jsonify([{'id': a['id'], 'name': a['name'], 'nationality': a.get('nationality'), 'image_url': a.get('image_url')} for a in results])

@app.route('/api/guess', methods=['POST'])
def api_guess():
    data = request.get_json()
    artist_id = data.get('artist_id')
    result = make_guess(artist_id)
    if 'guess' in result and 'artist' in result['guess']:
        artist = result['guess']['artist']
        if 'genres' not in artist or not isinstance(artist.get('genres'), list):
            raw = RAW_ARTISTS_BY_ID.get(artist_id)
            if raw and isinstance(raw.get('genres'), list):
                artist['genres'] = list(raw['genres'])
                artist['genre'] = raw['genres'][0] if raw['genres'] else None
            else:
                artist['genres'] = [artist['genre']] if artist.get('genre') else []
    return jsonify(result)

@app.route('/api/answer')
def api_answer():
    if session.get('status') not in ['won', 'lost']:
        return jsonify({'error': 'Game still in progress'}), 403
    return jsonify(ARTISTS_BY_ID.get(session['correct_artist_id']))

@app.route('/api/debug/answer')
def api_debug_answer():
    correct = ARTISTS_BY_ID.get(session.get('correct_artist_id')) or get_daily_artist()
    return jsonify(correct)

@app.route('/api/reset', methods=['POST'])
def api_reset():
    session.clear()
    return jsonify({'message': 'Game reset', 'status': 'ok'})

@app.route('/api/debug/artist/<artist_id>')
def api_debug_artist(artist_id):
    artist = ARTISTS_BY_ID.get(artist_id)
    return jsonify(artist if artist else {'error': 'Not found'})

@app.route('/api/next-reset')
def api_next_reset():
    now = get_turkey_now()
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if (now.hour, now.minute, now.second) != (0, 0, 0):
        tomorrow = tomorrow + timedelta(days=1)
    return jsonify({
        'seconds_remaining': int((tomorrow - now).total_seconds()),
        'turkey_time': now.strftime('%H:%M:%S'),
        'reset_at': '00:00 Turkey Time'
    })

# ============================================================
# Routes: SportsGuesser (sub-content)
# ============================================================

@app.route('/sportsguesser')
def sportsguesser_redirect():
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
        return jsonify(json.load(f))

@app.route('/sportsguesser/<path:subpath>')
def sportsguesser_static(subpath):
    if not sportsguesser_available():
        return jsonify({'error': 'Not found'}), 404
    path = os.path.join(SPORTSGUESSER_WEB, subpath)
    if not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(SPORTSGUESSER_WEB, subpath)

# ============================================================
# Load data (must run on import so gunicorn has artist data)
# ============================================================

load_artists()

# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    print(f"\n{'='*50}")
    print("Harman Games")
    print(f"{'='*50}")
    print(f"Hub: http://localhost:{port}/")
    print(f"Trackzy: http://localhost:{port}/trackzy")
    print(f"SportsGuesser: http://localhost:{port}/sportsguesser/")
    print(f"{'='*50}\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
