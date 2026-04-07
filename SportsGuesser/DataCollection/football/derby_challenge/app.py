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

from search_util import format_suggestion_list, matches_name_query, best_match_score
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


def _score_resolved(st: Dict[str, Any]) -> bool:
    return bool(st["solved"]["score"] or st["revealed"]["score"])


def _is_red_like_card(card_type: Optional[str]) -> bool:
    ct = (card_type or "yellow").strip().lower()
    return ct in ("red", "yellowred")


def _minute_label(ev: Dict[str, Any]) -> str:
    m = ev.get("minute")
    at = ev.get("added_time")
    if at is not None and str(at).strip() != "":
        return f"{m}' +{at}"
    return f"{m}'"


def _ev_sort_key(ev: Dict[str, Any], kind_prio: int, tie: int) -> tuple:
    m = int(ev.get("minute") or 0)
    at = ev.get("added_time")
    add = int(at) if at is not None and str(at).strip().isdigit() else 0
    return (m, add, kind_prio, tie)


def _build_team_hint_lines(truth: Dict[str, Any], is_home: bool) -> List[str]:
    rows: List[tuple] = []
    for i, c in enumerate(truth["cards"]):
        if bool(c.get("is_home")) != is_home:
            continue
        if _is_red_like_card(c.get("card_type")):
            continue
        lab = _minute_label(c)
        who = (c.get("player") or "").strip()
        rows.append((_ev_sort_key(c, 1, i), f"{lab} · Sarı kart: {who}"))
    for i, s in enumerate(truth["subs"]):
        if bool(s.get("is_home")) != is_home:
            continue
        lab = _minute_label(s)
        pin = (s.get("player_in") or "").strip()
        pout = (s.get("player_out") or "").strip()
        rows.append((_ev_sort_key(s, 2, i), f"{lab} · Değişiklik: {pout} → {pin}"))
    rows.sort(key=lambda x: x[0])
    return [r[1] for r in rows]


def _red_card_indices(truth: Dict[str, Any]) -> List[int]:
    return [
        i
        for i, c in enumerate(truth["cards"])
        if _is_red_like_card(c.get("card_type"))
    ]


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
        "hint_index_home": 0,
        "hint_index_away": 0,
        "hint_schedule_home": _build_team_hint_lines(truth, True),
        "hint_schedule_away": _build_team_hint_lines(truth, False),
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
        return jsonify({"ok": True, "correct": True, "message": "Zaten doğru."})

    try:
        h = int(hs)
        a = int(aw)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Sayı girin."})

    t = st["truth"]
    ok = h == t["home_score"] and a == t["away_score"]
    if ok:
        st["solved"]["score"] = True
    return jsonify({"ok": True, "correct": ok})


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
    if not _score_resolved(st):
        return jsonify(
            {"ok": False, "error": "Önce skoru tahmin edin veya skor ipucunu kullanın."}
        ), 400
    goals = st["truth"]["goals"]
    if idx < 0 or idx >= len(goals):
        return jsonify({"ok": False, "error": "Geçersiz gol."}), 400
    if idx in st["revealed"]["goals"]:
        return jsonify({"ok": False, "error": "Bu gol ipucu ile açıldı."})
    if idx in st["solved"]["goals"]:
        return jsonify({"ok": True, "correct": True})

    truth_name = goals[idx]["scorer"]
    ok = _name_match(truth_name, name)
    if ok:
        st["solved"]["goals"].add(idx)
    return jsonify({"ok": True, "correct": ok})


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
    if not _score_resolved(st):
        return jsonify(
            {"ok": False, "error": "Önce skoru tahmin edin veya skor ipucunu kullanın."}
        ), 400
    cards = st["truth"]["cards"]
    if idx < 0 or idx >= len(cards):
        return jsonify({"ok": False, "error": "Geçersiz kart."}), 400
    c = cards[idx]
    if not _is_red_like_card(c.get("card_type")):
        return jsonify(
            {
                "ok": False,
                "error": "Sarı kartlar yalnızca takım ipuçlarından görünür; tahmin sadece kırmızı kartlar içindir.",
            }
        )
    if idx in st["revealed"]["cards"]:
        return jsonify({"ok": False, "error": "Bu kart ipucu ile açıldı."})
    if idx in st["solved"]["cards"]:
        return jsonify({"ok": True, "correct": True})

    truth_name = c["player"]
    ok = _name_match(truth_name, name)
    if ok:
        st["solved"]["cards"].add(idx)
    return jsonify({"ok": True, "correct": ok})


@derby_bp.route("/api/guess-sub", methods=["POST"])
def guess_sub():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    if gid not in GAMES:
        return jsonify({"ok": False, "error": "Oyun yok."}), 400
    return jsonify(
        {
            "ok": False,
            "error": "Oyuncu değişiklikleri yalnızca takım ipuçlarından görüntülenir.",
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

    if not _score_resolved(st):
        return jsonify({"error": "Önce skoru tahmin edin veya skor ipucunu kullanın."}), 400

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
        c = t["cards"][idx]
        if not _is_red_like_card(c.get("card_type")):
            return jsonify(
                {"error": "Sarı kart ipuçları takım butonlarından verilir."}
            ), 400
        st["revealed"]["cards"].add(idx)
        return jsonify({"kind": "card", "idx": idx, "player": c["player"]})

    if kind == "sub":
        return jsonify(
            {"error": "Oyuncu değişiklikleri takım ipuçlarından görüntülenir."}
        ), 400

    return jsonify({"error": "Bilinmeyen tür."}), 400


@derby_bp.route("/api/team-hint", methods=["POST"])
def team_hint():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    side = (body.get("side") or "").lower()
    advance = bool(body.get("advance"))
    if gid not in GAMES:
        return jsonify({"ok": False, "error": "Oyun yok."}), 400
    if side not in ("home", "away"):
        return jsonify({"ok": False, "error": "Geçersiz taraf."}), 400
    st = GAMES[gid]
    key = "hint_index_home" if side == "home" else "hint_index_away"
    sk = "hint_schedule_home" if side == "home" else "hint_schedule_away"
    sched: List[str] = st[sk]
    idx = st[key]
    if advance:
        if idx >= len(sched):
            return jsonify(
                {
                    "ok": False,
                    "error": "Bu takım için ipucu kalmadı.",
                    "pages": sched[:idx],
                    "focus": max(0, idx - 1) if idx else 0,
                    "has_more": False,
                    "total": len(sched),
                }
            )
        idx += 1
        st[key] = idx
    pages = sched[: st[key]]
    foc = max(0, len(pages) - 1) if pages else 0
    return jsonify(
        {
            "ok": True,
            "side": side,
            "pages": pages,
            "focus": foc,
            "has_more": st[key] < len(sched),
            "total": len(sched),
        }
    )


@derby_bp.route("/api/reveal-all", methods=["POST"])
def reveal_all():
    """Oyunu bitir: skor, tüm gol/kırmızı kart ipuçları ve takım ipucu kuyruklarını tamamen aç."""
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    if gid not in GAMES:
        return jsonify({"ok": False, "error": "Oyun yok."}), 400
    st = GAMES[gid]
    t = st["truth"]

    st["revealed"]["score"] = True
    for i in range(len(t["goals"])):
        st["revealed"]["goals"].add(i)
    for i in _red_card_indices(t):
        st["revealed"]["cards"].add(i)

    st["hint_index_home"] = len(st["hint_schedule_home"])
    st["hint_index_away"] = len(st["hint_schedule_away"])

    goals_out = [{"idx": i, "scorer": g["scorer"]} for i, g in enumerate(t["goals"])]
    reds = _red_card_indices(t)
    cards_out = [{"idx": i, "player": t["cards"][i]["player"]} for i in reds]

    return jsonify(
        {
            "ok": True,
            "home_score": t["home_score"],
            "away_score": t["away_score"],
            "goals": goals_out,
            "red_cards": cards_out,
            "team_hints_home": list(st["hint_schedule_home"]),
            "team_hints_away": list(st["hint_schedule_away"]),
        }
    )


@derby_bp.route("/api/finish", methods=["POST"])
def finish():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    if gid not in GAMES:
        return jsonify({"error": "Oyun yok."}), 400
    del GAMES[gid]
    return jsonify({"message": "Oyun bitti."})


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
    out = format_suggestion_list(
        rows,
        limit=14,
        nationality_for=lambda pid: players[pid].primary_nationality(),
    )
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
    n_g = len(t["goals"])
    red_ix = _red_card_indices(t)

    score_done = st["revealed"]["score"] or st["solved"]["score"]
    goals_done = all(
        i in st["revealed"]["goals"] or i in st["solved"]["goals"] for i in range(n_g)
    )
    cards_done = all(
        i in st["revealed"]["cards"] or i in st["solved"]["cards"] for i in red_ix
    )

    done = score_done and goals_done and cards_done
    return jsonify({"done": done})


def create_standalone_app():
    from flask import Flask

    application = Flask(__name__)
    application.config["JSON_AS_ASCII"] = False
    application.register_blueprint(derby_bp, url_prefix="")
    return application


if __name__ == "__main__":
    app = create_standalone_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5051)), debug=True)
