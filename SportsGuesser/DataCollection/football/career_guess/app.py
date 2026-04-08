"""
Kariyer tahmini — Süper Lig kariyer tablosundan oyuncu bulma (sınırsız tahmin).
Blueprint: /sportsguesser/football/career/
"""

from __future__ import annotations

import os
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, render_template, request, session

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
PLAYER_GUESS = os.path.join(ROOT, "..", "player_guess")
if PLAYER_GUESS not in sys.path:
    sys.path.insert(0, PLAYER_GUESS)
GRID_GAME = os.path.join(ROOT, "..", "grid_game")
if GRID_GAME not in sys.path:
    sys.path.insert(0, GRID_GAME)

from catalog import (  # noqa: E402
    DEFAULT_DATA,
    cache_path,
    load_catalog,
    player_by_id,
)
from search_util import best_match_score, format_suggestion_list, matches_name_query  # noqa: E402
from season_goals import build_season_goals_map  # noqa: E402

career_guess_bp = Blueprint(
    "career_guess",
    __name__,
    root_path=ROOT,
    static_folder="static",
    template_folder="templates",
)

SESSION_KEY = "football_career_guess"

_POOL: Optional[List[Dict[str, Any]]] = None
_ELIGIBLE_IDS: Optional[List[int]] = None
_BY_ID: Optional[Dict[int, Dict[str, Any]]] = None
_SEASON_GOALS: Optional[Dict[Tuple[int, str], int]] = None
_CATALOG_MTIME: Optional[float] = None


def get_data_root() -> str:
    return os.path.abspath(os.environ.get("SUPERLIG_DATA", DEFAULT_DATA))


def _ensure_pool() -> None:
    global _POOL, _ELIGIBLE_IDS, _BY_ID, _CATALOG_MTIME, _SEASON_GOALS
    cp = cache_path()
    mtime = os.path.getmtime(cp) if os.path.isfile(cp) else None
    if _POOL is None or mtime != _CATALOG_MTIME:
        pool, eligible_ids, _ = load_catalog(get_data_root())
        _POOL = pool
        _ELIGIBLE_IDS = eligible_ids
        _BY_ID = player_by_id(pool)
        _CATALOG_MTIME = os.path.getmtime(cp) if os.path.isfile(cp) else None
        _SEASON_GOALS = build_season_goals_map(get_data_root())


def _season_sort_key(sk: str) -> int:
    part = sk.split("-")[0] if sk else ""
    return int(part) if part.isdigit() else 0


def _career_rows_for_player(pid: int, player: Dict[str, Any]) -> List[Dict[str, Any]]:
    timeline = player.get("career_timeline") or []
    by_season: Dict[str, List[str]] = {}
    for row in timeline:
        s = row.get("season") or ""
        t = (row.get("team") or "").strip()
        if not s:
            continue
        by_season.setdefault(s, []).append(t)
    sg = _SEASON_GOALS or {}
    rows: List[Dict[str, Any]] = []
    for season in sorted(by_season.keys(), key=_season_sort_key):
        teams = " · ".join(sorted(set(by_season[season])))
        g = int(sg.get((pid, season), 0))
        rows.append({"season": season, "teams": teams, "goals": g})
    return rows


def _pick_random_target_id() -> Optional[int]:
    _ensure_pool()
    if not _ELIGIBLE_IDS:
        return None
    return random.choice(_ELIGIBLE_IDS)


def _session_bucket() -> Dict[str, Any]:
    if SESSION_KEY not in session:
        session[SESSION_KEY] = {}
    return session[SESSION_KEY]


def _start_new_round() -> None:
    b = _session_bucket()
    tid = _pick_random_target_id()
    b["target_id"] = tid
    b["guesses"] = []
    b["status"] = "playing"
    b["goals_revealed"] = False
    b["profile_step"] = 0
    session.modified = True


def _public_guess_row(pl: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "player_id": pl["player_id"],
        "name": pl["name"],
        "short_name": pl.get("short_name") or pl["name"],
        "nationality": pl.get("nationality") or "",
    }


def _pos_label(p: Optional[str]) -> str:
    m = {"G": "KL", "D": "DF", "M": "OS", "F": "FW"}
    if not p:
        return "?"
    c = p.strip().upper()[:1]
    return m.get(c, c or "?")


def get_game_state(for_client: bool = True) -> Dict[str, Any]:
    _ensure_pool()
    b = _session_bucket()
    if not b.get("target_id"):
        _start_new_round()

    tid = b.get("target_id")
    target = _BY_ID.get(tid) if tid and _BY_ID else None
    goals_rev = bool(b.get("goals_revealed"))
    step = int(b.get("profile_step") or 0)

    career_rows: List[Dict[str, Any]] = []
    if target and tid:
        for r in _career_rows_for_player(int(tid), target):
            row = dict(r)
            if for_client and not goals_rev:
                row["goals"] = None
            career_rows.append(row)

    profile_hints: Dict[str, Any] = {
        "position": _pos_label(target.get("position")) if target and step >= 1 else None,
        "birth_year": target.get("birth_year") if target and step >= 2 else None,
        "nationality": target.get("nationality") if target and step >= 3 else None,
    }

    guesses_out: List[Dict[str, Any]] = []
    for item in b.get("guesses", []):
        pid = item.get("player_id")
        pl = _BY_ID.get(pid) if _BY_ID and pid is not None else None
        if not pl:
            continue
        guesses_out.append(
            {
                "player": _public_guess_row(pl),
                "correct": bool(item.get("correct")),
            }
        )

    answer = None
    if target and tid and b.get("status") == "lost":
        answer = _public_guess_row(target)

    return {
        "status": b.get("status", "playing"),
        "career_rows": career_rows,
        "goals_revealed": goals_rev,
        "profile_hints": profile_hints,
        "profile_step": step,
        "profile_max_step": 3,
        "guesses": guesses_out,
        "answer": answer,
    }


def search_players(query: str, limit: int = 12) -> List[Dict[str, Any]]:
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


@career_guess_bp.route("/")
def index():
    """Her tam sayfa yüklemesinde yeni hedef oyuncu."""
    _start_new_round()
    return render_template("career_guess.html")


@career_guess_bp.route("/api/state")
def api_state():
    return jsonify(get_game_state())


@career_guess_bp.route("/api/search")
def api_search():
    q = request.args.get("q", "")
    return jsonify(search_players(q))


@career_guess_bp.route("/api/guess", methods=["POST"])
def api_guess():
    _ensure_pool()
    data = request.get_json(force=True, silent=True) or {}
    try:
        pid = int(data.get("player_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Geçersiz oyuncu"}), 400

    b = _session_bucket()
    if not b.get("target_id"):
        _start_new_round()
    tid = b.get("target_id")
    if tid is None:
        return jsonify({"error": "Hedef yok"}), 400

    if b.get("status") in ("won", "lost"):
        return jsonify({"error": "Oyun bitti"}), 400

    guessed = _BY_ID.get(pid)
    if not guessed:
        return jsonify({"error": "Oyuncu bulunamadı"}), 404

    correct = pid == int(tid)
    if any(int(x.get("player_id")) == pid for x in b.get("guesses", [])):
        return jsonify({"error": "Bu oyuncu zaten seçildi"}), 400

    b.setdefault("guesses", [])
    b["guesses"].append({"player_id": pid, "correct": correct})
    if correct:
        b["status"] = "won"
    session.modified = True
    return jsonify({"ok": True, **get_game_state()})


@career_guess_bp.route("/api/hint/goals", methods=["POST"])
def api_hint_goals():
    b = _session_bucket()
    if not b.get("target_id"):
        return jsonify({"error": "Oyun yok"}), 400
    b["goals_revealed"] = True
    session.modified = True
    return jsonify({"ok": True, **get_game_state()})


@career_guess_bp.route("/api/hint/profile", methods=["POST"])
def api_hint_profile():
    b = _session_bucket()
    if not b.get("target_id"):
        return jsonify({"error": "Oyun yok"}), 400
    step = int(b.get("profile_step") or 0)
    if step < 3:
        b["profile_step"] = step + 1
    session.modified = True
    return jsonify({"ok": True, **get_game_state()})


@career_guess_bp.route("/api/surrender", methods=["POST"])
def api_surrender():
    _ensure_pool()
    b = _session_bucket()
    if not b.get("target_id"):
        return jsonify({"error": "Oyun yok"}), 400
    if b.get("status") == "won":
        return jsonify({"ok": True, **get_game_state()})
    if b.get("status") != "lost":
        b["status"] = "lost"
        session.modified = True
    return jsonify({"ok": True, **get_game_state()})


def create_app():
    from flask import Flask

    application = Flask(__name__)
    application.register_blueprint(career_guess_bp, url_prefix="/career")
    return application


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5054)), debug=True)
