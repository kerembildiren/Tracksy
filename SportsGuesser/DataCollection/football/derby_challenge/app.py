"""
Derbi Challenge — Flask blueprint (/sportsguesser/football/derby).
"""

from __future__ import annotations

import copy
import os
import random
import sys
import uuid
from typing import Any, Dict, List, Optional, Set

from flask import Blueprint, jsonify, render_template, request

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
GRID_ROOT = os.path.join(ROOT, "..", "grid_game")
if GRID_ROOT not in sys.path:
    sys.path.insert(0, GRID_ROOT)

from search_util import matches_name_query, best_match_score
from player_index import load_or_build_index, PlayerRecord

from data import load_derby_bundle, public_challenge_payload

DEFAULT_DATA = os.path.join(ROOT, "..", "superlig_data")

derby_bp = Blueprint(
    "derby_challenge",
    __name__,
    root_path=ROOT,
    static_folder="static",
    template_folder="templates",
)

POINTS_SCORE = 100
POINTS_GOAL = 100
POINTS_CARD = 200
POINTS_SUB = 100

SUGGEST_MIN = 2

_data_root: Optional[str] = None
_bundle_matches: Optional[List[Dict[str, Any]]] = None
_players: Optional[Dict[int, PlayerRecord]] = None

GAMES: Dict[str, Dict[str, Any]] = {}


def get_data_root() -> str:
    global _data_root
    if _data_root is None:
        _data_root = os.environ.get("SUPERLIG_DATA", DEFAULT_DATA)
    return os.path.abspath(_data_root)


def get_bundle_matches() -> List[Dict[str, Any]]:
    global _bundle_matches
    if _bundle_matches is None:
        _bundle_matches = load_derby_bundle()
    return _bundle_matches


def get_players() -> Dict[int, PlayerRecord]:
    global _players
    if _players is None:
        _players, _ = load_or_build_index(get_data_root())
    return _players


def _name_match(truth: str, guess: str) -> bool:
    if not truth or not (guess or "").strip():
        return False
    return matches_name_query(truth, guess.strip())


@derby_bp.route("/")
def index():
    return render_template("derby.html")


@derby_bp.route("/api/new-game", methods=["POST"])
def new_game():
    matches = get_bundle_matches()
    if not matches:
        return jsonify(
            {
                "error": "Derbi verisi yok. Projede derby_challenge/build_derby_bundle.py çalıştırıp bundled/derbies.json oluşturun.",
            }
        ), 400
    truth = copy.deepcopy(random.choice(matches))
    if not truth.get("home_team"):
        return jsonify({"error": "Maç yüklenemedi."}), 400

    gid = str(uuid.uuid4())
    GAMES[gid] = {
        "truth": truth,
        "revealed": {
            "score": False,
            "goals": set(),
            "cards": set(),
            "subs": set(),
        },
        "solved": {
            "score": False,
            "goals": set(),
            "cards": set(),
            "subs": set(),
        },
        "points": 0,
    }
    pub = public_challenge_payload(truth)
    pub["game_id"] = gid
    return jsonify(pub)


@derby_bp.route("/api/guess-score", methods=["POST"])
def guess_score():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    hs = body.get("home_score")
    aw = body.get("away_score")
    if gid not in GAMES:
        return jsonify({"ok": False, "error": "Oyun yok."}), 400
    st = GAMES[gid]
    if st["revealed"]["score"]:
        return jsonify({"ok": False, "error": "Skor alanı ipucu ile açıldı."})
    if st["solved"]["score"]:
        return jsonify({"ok": True, "correct": True, "points": 0, "message": "Zaten doğru."})

    try:
        h = int(hs)
        a = int(aw)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Sayı girin."})

    t = st["truth"]
    ok = h == t["home_score"] and a == t["away_score"]
    pts = 0
    if ok:
        st["solved"]["score"] = True
        pts = POINTS_SCORE
        st["points"] += pts
    return jsonify(
        {
            "ok": True,
            "correct": ok,
            "points": pts,
            "total_points": st["points"],
        }
    )


@derby_bp.route("/api/guess-goal", methods=["POST"])
def guess_goal():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    idx = body.get("idx")
    name = body.get("name", "")
    if gid not in GAMES:
        return jsonify({"ok": False, "error": "Oyun yok."}), 400
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Geçersiz."}), 400

    st = GAMES[gid]
    goals = st["truth"]["goals"]
    if idx < 0 or idx >= len(goals):
        return jsonify({"ok": False, "error": "Geçersiz gol."}), 400
    if idx in st["revealed"]["goals"]:
        return jsonify({"ok": False, "error": "Bu gol ipucu ile açıldı."})
    if idx in st["solved"]["goals"]:
        return jsonify({"ok": True, "correct": True, "points": 0})

    truth_name = goals[idx]["scorer"]
    ok = _name_match(truth_name, name)
    pts = 0
    if ok:
        st["solved"]["goals"].add(idx)
        pts = POINTS_GOAL
        st["points"] += pts
    return jsonify(
        {
            "ok": True,
            "correct": ok,
            "points": pts,
            "total_points": st["points"],
        }
    )


@derby_bp.route("/api/guess-card", methods=["POST"])
def guess_card():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    idx = body.get("idx")
    name = body.get("name", "")
    if gid not in GAMES:
        return jsonify({"ok": False, "error": "Oyun yok."}), 400
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Geçersiz."}), 400

    st = GAMES[gid]
    cards = st["truth"]["cards"]
    if idx < 0 or idx >= len(cards):
        return jsonify({"ok": False, "error": "Geçersiz kart."}), 400
    if idx in st["revealed"]["cards"]:
        return jsonify({"ok": False, "error": "Bu kart ipucu ile açıldı."})
    if idx in st["solved"]["cards"]:
        return jsonify({"ok": True, "correct": True, "points": 0})

    truth_name = cards[idx]["player"]
    ok = _name_match(truth_name, name)
    pts = 0
    if ok:
        st["solved"]["cards"].add(idx)
        pts = POINTS_CARD
        st["points"] += pts
    return jsonify(
        {
            "ok": True,
            "correct": ok,
            "points": pts,
            "total_points": st["points"],
        }
    )


@derby_bp.route("/api/guess-sub", methods=["POST"])
def guess_sub():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    idx = body.get("idx")
    pin = body.get("player_in", "")
    pout = body.get("player_out", "")
    if gid not in GAMES:
        return jsonify({"ok": False, "error": "Oyun yok."}), 400
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Geçersiz."}), 400

    st = GAMES[gid]
    subs = st["truth"]["subs"]
    if idx < 0 or idx >= len(subs):
        return jsonify({"ok": False, "error": "Geçersiz değişiklik."}), 400
    if idx in st["revealed"]["subs"]:
        return jsonify({"ok": False, "error": "Bu değişiklik ipucu ile açıldı."})
    if idx in st["solved"]["subs"]:
        return jsonify({"ok": True, "correct": True, "points": 0})

    s = subs[idx]
    ok_in = _name_match(s["player_in"], pin)
    ok_out = _name_match(s["player_out"], pout)
    ok = ok_in and ok_out
    pts = 0
    if ok:
        st["solved"]["subs"].add(idx)
        pts = POINTS_SUB
        st["points"] += pts
    return jsonify(
        {
            "ok": True,
            "correct": ok,
            "correct_in": ok_in,
            "correct_out": ok_out,
            "points": pts,
            "total_points": st["points"],
        }
    )


@derby_bp.route("/api/reveal", methods=["POST"])
def reveal():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    kind = body.get("kind")
    idx = body.get("idx")
    if gid not in GAMES:
        return jsonify({"error": "Oyun yok."}), 400
    st = GAMES[gid]
    t = st["truth"]

    if kind == "score":
        if st["revealed"]["score"]:
            return jsonify(
                {
                    "kind": "score",
                    "home_score": t["home_score"],
                    "away_score": t["away_score"],
                }
            )
        st["revealed"]["score"] = True
        return jsonify(
            {
                "kind": "score",
                "home_score": t["home_score"],
                "away_score": t["away_score"],
            }
        )

    try:
        idx = int(idx)
    except (TypeError, ValueError):
        return jsonify({"error": "Geçersiz."}), 400

    if kind == "goal":
        if idx < 0 or idx >= len(t["goals"]):
            return jsonify({"error": "Geçersiz."}), 400
        st["revealed"]["goals"].add(idx)
        g = t["goals"][idx]
        return jsonify({"kind": "goal", "idx": idx, "scorer": g["scorer"]})

    if kind == "card":
        if idx < 0 or idx >= len(t["cards"]):
            return jsonify({"error": "Geçersiz."}), 400
        st["revealed"]["cards"].add(idx)
        c = t["cards"][idx]
        return jsonify({"kind": "card", "idx": idx, "player": c["player"]})

    if kind == "sub":
        if idx < 0 or idx >= len(t["subs"]):
            return jsonify({"error": "Geçersiz."}), 400
        st["revealed"]["subs"].add(idx)
        s = t["subs"][idx]
        return jsonify(
            {
                "kind": "sub",
                "idx": idx,
                "player_in": s["player_in"],
                "player_out": s["player_out"],
            }
        )

    return jsonify({"error": "Bilinmeyen tür."}), 400


@derby_bp.route("/api/finish", methods=["POST"])
def finish():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    if gid not in GAMES:
        return jsonify({"error": "Oyun yok."}), 400
    st = GAMES[gid]
    total = st["points"]
    del GAMES[gid]
    return jsonify({"total_points": total, "message": "Oyun bitti."})


@derby_bp.route("/api/suggest", methods=["POST"])
def suggest():
    body = request.get_json(force=True, silent=True) or {}
    q = (body.get("q") or "").strip()
    if len(q) < SUGGEST_MIN:
        return jsonify({"suggestions": []})
    players = get_players()
    rows: List[tuple] = []
    for pid, r in players.items():
        name = r.name or r.short_name
        if not name:
            continue
        if not matches_name_query(name, q):
            continue
        sc = best_match_score(name, q)
        rows.append((-sc, name.lower(), name, pid))
    rows.sort(key=lambda x: (x[0], x[2]))
    out = [{"id": p, "name": n} for _, _, n, p in rows[:14]]
    return jsonify({"suggestions": out})


@derby_bp.route("/api/status", methods=["POST"])
def status():
    """Bitiş kontrolü: tüm alanlar çözüldü veya ipucu."""
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    if gid not in GAMES:
        return jsonify({"done": True})
    st = GAMES[gid]
    t = st["truth"]
    n_g, n_c, n_s = len(t["goals"]), len(t["cards"]), len(t["subs"])

    score_done = st["revealed"]["score"] or st["solved"]["score"]
    goals_done = all(
        i in st["revealed"]["goals"] or i in st["solved"]["goals"] for i in range(n_g)
    )
    cards_done = all(
        i in st["revealed"]["cards"] or i in st["solved"]["cards"] for i in range(n_c)
    )
    subs_done = all(
        i in st["revealed"]["subs"] or i in st["solved"]["subs"] for i in range(n_s)
    )

    done = score_done and goals_done and cards_done and subs_done
    return jsonify({"done": done, "total_points": st["points"]})


def create_standalone_app():
    from flask import Flask

    application = Flask(__name__)
    application.config["JSON_AS_ASCII"] = False
    application.register_blueprint(derby_bp, url_prefix="")
    return application


if __name__ == "__main__":
    app = create_standalone_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5051)), debug=True)
