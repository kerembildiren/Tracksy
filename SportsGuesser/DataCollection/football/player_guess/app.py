"""
Süper Lig daily player guess (Trackzy-style) — blueprint /sportsguesser/football/guess
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz
from flask import Blueprint, jsonify, render_template, request, session

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
GRID_GAME = os.path.join(ROOT, "..", "grid_game")
if GRID_GAME not in sys.path:
    sys.path.insert(0, GRID_GAME)

from catalog import DEFAULT_DATA, cache_path, load_catalog, player_by_id
from search_util import best_match_score, format_suggestion_list, matches_name_query
from geo import continent_for_nationality

player_guess_bp = Blueprint(
    "player_guess",
    __name__,
    root_path=ROOT,
    static_folder="static",
    template_folder="templates",
)

TURKEY_TZ = pytz.timezone("Europe/Istanbul")
EPOCH_DATE = datetime(2025, 1, 1)

_POOL: Optional[List[Dict[str, Any]]] = None
_ELIGIBLE_IDS: Optional[List[int]] = None
_BY_ID: Optional[Dict[int, Dict[str, Any]]] = None
_CATALOG_MTIME: Optional[float] = None


def get_data_root() -> str:
    return os.path.abspath(os.environ.get("SUPERLIG_DATA", DEFAULT_DATA))


def _ensure_pool() -> None:
    global _POOL, _ELIGIBLE_IDS, _BY_ID, _CATALOG_MTIME
    cp = cache_path()
    mtime = os.path.getmtime(cp) if os.path.isfile(cp) else None
    if _POOL is None or mtime != _CATALOG_MTIME:
        pool, eligible_ids, _ = load_catalog(get_data_root())
        _POOL = pool
        _ELIGIBLE_IDS = eligible_ids
        _BY_ID = player_by_id(pool)
        _CATALOG_MTIME = os.path.getmtime(cp) if os.path.isfile(cp) else None


def get_turkey_now():
    return datetime.now(TURKEY_TZ)


def get_date_string() -> str:
    return get_turkey_now().strftime("%Y-%m-%d")


def seconds_until_turkey_midnight() -> int:
    """Günlük oyuncu yenilenmesi: Türkiye saatiyle bir sonraki gece yarısına kalan saniye."""
    now = get_turkey_now()
    next_mid = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return max(0, int((next_mid - now).total_seconds()))


def demo_reveal_enabled() -> bool:
    return os.environ.get("PLAYER_GUESS_DEMO_REVEAL", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def get_daily_player() -> Optional[Dict[str, Any]]:
    """Daily answer: only players meeting catalog eligibility (G+A / seasons / title)."""
    _ensure_pool()
    if not _ELIGIBLE_IDS or not _BY_ID:
        return None
    days_since_epoch = (get_turkey_now().date() - EPOCH_DATE.date()).days
    seed = abs(days_since_epoch)
    hash_val = (seed * 6364136223846793005 + 1442695040888963407) % (2**64)
    pid = _ELIGIBLE_IDS[hash_val % len(_ELIGIBLE_IDS)]
    return _BY_ID.get(pid)


def compare_numeric(
    guessed: Optional[int], correct: Optional[int], threshold: int
) -> Dict[str, Any]:
    if guessed is None or correct is None:
        return {"result": "unknown"}
    try:
        gn = int(guessed)
        cn = int(correct)
    except (TypeError, ValueError):
        return {"result": "unknown"}
    if gn == cn:
        return {"result": "correct"}
    diff = abs(gn - cn)
    direction = "higher" if cn > gn else "lower"
    if diff <= threshold:
        return {"result": "close", "direction": direction}
    return {"result": direction}


def compare_position_exact(guessed: Optional[str], correct: Optional[str]) -> Dict[str, Any]:
    """Green only on exact G/D/M/F match — no directional hint."""
    if not guessed or not correct:
        return {"result": "unknown"}
    g = guessed.strip().upper()[:1]
    c = correct.strip().upper()[:1]
    valid = {"G", "D", "M", "F"}
    if g not in valid or c not in valid:
        return {"result": "unknown"}
    return {"result": "correct" if g == c else "incorrect"}


def compare_nationality(guessed: Optional[str], correct: Optional[str]) -> Dict[str, Any]:
    """Exact green; same continent yellow; else grey."""
    gs = (guessed or "").strip()
    cs = (correct or "").strip()
    if not gs or not cs:
        return {"result": "unknown"}
    if gs.lower() == cs.lower():
        return {"result": "correct"}
    cg = continent_for_nationality(gs)
    cc = continent_for_nationality(cs)
    if cg and cc and cg == cc:
        return {"result": "close"}
    return {"result": "incorrect"}


def compare_exact_ci(guessed: Optional[str], correct: Optional[str]) -> Dict[str, Any]:
    if guessed is None or correct is None:
        return {"result": "unknown"}
    return {
        "result": "correct" if guessed.strip().lower() == correct.strip().lower() else "incorrect"
    }


def compare_players(guessed: Dict[str, Any], correct: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if guessed["player_id"] == correct["player_id"]:
        return {
            k: {"result": "correct"}
            for k in (
                "position",
                "goals_assists",
                "birth_year",
                "nationality",
                "seasons_played",
                "top_club",
            )
        }
    return {
        "position": compare_position_exact(guessed.get("position"), correct.get("position")),
        "goals_assists": compare_numeric(
            guessed.get("goals_assists"), correct.get("goals_assists"), 10
        ),
        "birth_year": compare_numeric(
            guessed.get("birth_year"), correct.get("birth_year"), 5
        ),
        "nationality": compare_nationality(
            guessed.get("nationality"), correct.get("nationality")
        ),
        "seasons_played": compare_numeric(
            guessed.get("seasons_played"), correct.get("seasons_played"), 3
        ),
        "top_club": compare_exact_ci(
            guessed.get("top_club_name"), correct.get("top_club_name")
        ),
    }


def _session_bucket() -> Dict[str, Any]:
    if "football_player_guess" not in session:
        session["football_player_guess"] = {}
    return session["football_player_guess"]


def _public_player(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "player_id": p["player_id"],
        "name": p["name"],
        "short_name": p.get("short_name") or p["name"],
        "position": p.get("position") or "?",
        "birth_year": p.get("birth_year"),
        "nationality": p.get("nationality") or "",
        "seasons_played": p["seasons_played"],
        "goals_total": p["goals_total"],
        "assists_total": p["assists_total"],
        "goals_assists": p["goals_assists"],
        "top_club_name": p["top_club_name"],
    }


def get_game_state() -> Dict[str, Any]:
    _ensure_pool()
    b = _session_bucket()
    today = get_date_string()
    if not b.get("is_custom"):
        if b.get("game_date") != today or b.get("correct_player_id") is None:
            daily = get_daily_player()
            b["game_date"] = today
            b["correct_player_id"] = daily["player_id"] if daily else None
            b["guesses"] = []
            b["status"] = "playing"
            session.modified = True

    guesses_out: List[Dict[str, Any]] = []
    for g in b.get("guesses", []):
        pid = g.get("player_id")
        pl = _BY_ID.get(pid) if _BY_ID and pid is not None else None
        if not pl:
            continue
        guesses_out.append(
            {
                "player_id": pid,
                "player": _public_player(pl),
                "hints": g.get("hints", {}),
                "is_correct": g.get("is_correct", False),
            }
        )

    return {
        "date": b.get("game_date", today),
        "guesses": guesses_out,
        "status": b.get("status", "playing"),
        "remaining": 10 - len(b.get("guesses", [])),
        "seconds_until_refresh": seconds_until_turkey_midnight(),
        "demo_reveal": demo_reveal_enabled(),
    }


def make_guess(player_id: int) -> Dict[str, Any]:
    _ensure_pool()
    if not _BY_ID:
        return {"error": "Veri yüklenemedi"}
    b = _session_bucket()
    if b.get("status") != "playing":
        return {"error": "Oyun bitti"}
    if len(b.get("guesses", [])) >= 10:
        return {"error": "Tahmin hakkı bitti"}
    if any(x.get("player_id") == player_id for x in b.get("guesses", [])):
        return {"error": "Bu oyuncu zaten seçildi"}

    guessed = _BY_ID.get(player_id)
    cid = b.get("correct_player_id")
    correct = _BY_ID.get(cid) if cid is not None else None
    if not guessed:
        return {"error": "Oyuncu bulunamadı"}
    if not correct:
        return {"error": "Oyun yok"}

    hints = compare_players(guessed, correct)
    is_correct = guessed["player_id"] == correct["player_id"]
    rec = {
        "player_id": player_id,
        "hints": hints,
        "is_correct": is_correct,
    }
    b["guesses"] = b.get("guesses", []) + [rec]
    if is_correct:
        b["status"] = "won"
    elif len(b["guesses"]) >= 10:
        b["status"] = "lost"
    session.modified = True

    return {
        "guess": {
            "player_id": player_id,
            "player": _public_player(guessed),
            "hints": hints,
            "is_correct": is_correct,
        },
        "status": b["status"],
        "remaining": 10 - len(b["guesses"]),
    }


def search_players(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    _ensure_pool()
    if not _POOL:
        return []
    q = query.strip()
    if len(q) < 2:
        return []
    rows: List[tuple] = []
    for p in _POOL:
        display = (p.get("name") or "").strip() or (p.get("short_name") or "").strip()
        short = (p.get("short_name") or "").strip()
        if not display:
            continue
        ok = matches_name_query(display, q)
        if short and short != display:
            ok = ok or matches_name_query(short, q)
        if not ok:
            continue
        sc = best_match_score(display, q)
        if short and short != display:
            sc = max(sc, best_match_score(short, q))
        rows.append((-sc, display.lower(), display, int(p["player_id"])))
    rows.sort(key=lambda x: (x[0], x[2]))
    labeled = format_suggestion_list(
        rows,
        limit=limit,
        nationality_for=lambda pid: (_BY_ID.get(pid) or {}).get("nationality"),
    )
    out: List[Dict[str, Any]] = []
    for item in labeled:
        pid = int(item["id"])
        p = _BY_ID.get(pid) or {}
        out.append(
            {
                "player_id": pid,
                "name": str(item["name"]),
                "short_name": p.get("short_name") or p.get("name") or "",
                "nationality": p.get("nationality"),
            }
        )
    return out


@player_guess_bp.route("/")
def index():
    """Custom puzzle: ?player=123. Opening / without query clears a custom puzzle so the daily game applies."""
    _ensure_pool()
    raw = (request.args.get("player") or "").strip()
    if raw:
        try:
            pid = int(raw)
        except ValueError:
            pid = None
        if pid is not None and _BY_ID and pid in _BY_ID:
            b = _session_bucket()
            b.clear()
            b["is_custom"] = True
            b["game_date"] = "custom"
            b["correct_player_id"] = pid
            b["guesses"] = []
            b["status"] = "playing"
            session.modified = True
    else:
        b = _session_bucket()
        if b.get("is_custom"):
            session["football_player_guess"] = {}
            session.modified = True
    return render_template("player_guess.html")


@player_guess_bp.route("/api/state")
def api_state():
    return jsonify(get_game_state())


@player_guess_bp.route("/api/search")
def api_search():
    q = request.args.get("q", "")
    return jsonify(search_players(q))


@player_guess_bp.route("/api/guess", methods=["POST"])
def api_guess():
    data = request.get_json(force=True, silent=True) or {}
    pid = data.get("player_id")
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return jsonify({"error": "Geçersiz oyuncu"}), 400
    result = make_guess(pid)
    if "error" in result and "guess" not in result:
        return jsonify(result), 400
    return jsonify(result)


@player_guess_bp.route("/api/reset", methods=["POST"])
def api_reset():
    """Aynı gün / aynı özel bulmaca için tahminleri sıfırla (hedef oyuncu aynı kalır)."""
    _ensure_pool()
    b = _session_bucket()
    b["guesses"] = []
    b["status"] = "playing"
    session.modified = True
    return jsonify(get_game_state())


@player_guess_bp.route("/api/demo-reveal")
def api_demo_reveal():
    """Demo: günün hedef ismi. PLAYER_GUESS_DEMO_REVEAL=1 ile açılır."""
    if not demo_reveal_enabled():
        return jsonify({"error": "Demo reveal kapalı."}), 403
    _ensure_pool()
    b = _session_bucket()
    cid = b.get("correct_player_id")
    if cid is None or not _BY_ID:
        return jsonify({"error": "Aktif oyun yok."}), 400
    c = _BY_ID.get(cid)
    if not c:
        return jsonify({"error": "Oyuncu bulunamadı."}), 404
    return jsonify({"name": c.get("name") or c.get("short_name") or str(cid)})


@player_guess_bp.route("/api/answer")
def api_answer():
    b = _session_bucket()
    if b.get("status") not in ("won", "lost"):
        return jsonify({"error": "Oyun sürüyor"}), 403
    cid = b.get("correct_player_id")
    if cid is None or not _BY_ID:
        return jsonify({}), 404
    c = _BY_ID.get(cid)
    return jsonify(_public_player(c) if c else {})


def create_app():
    from flask import Flask

    application = Flask(__name__)
    application.register_blueprint(player_guess_bp, url_prefix="/guess")
    return application


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5053)), debug=True)
