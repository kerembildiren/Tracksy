"""
Flask server for the Süper Lig grid game.
Can run standalone or register as blueprint on HarmanGames (url_prefix /sportsguesser/football).
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import Any, Dict, List, Optional, Set

from flask import Blueprint, Flask, jsonify, render_template, request

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from player_index import PlayerRecord, load_or_build_index
from generator import try_generate, Criterion
from search_util import matches_name_query, best_match_score

DEFAULT_DATA = os.path.join(ROOT, "..", "superlig_data")

# Explicit root_path so templates resolve when this module is loaded via importlib (HarmanGames).
football_grid_bp = Blueprint(
    "football_grid",
    __name__,
    root_path=ROOT,
    static_folder="static",
    template_folder="templates",
)

# Autocomplete: tüm veri seti; en az bu kadar harf yoksa öneri yok (havuz sızdırmaz)
SUGGEST_MIN_CHARS = 3

_players: Optional[Dict[int, PlayerRecord]] = None
_team_names: Optional[Dict[int, str]] = None

GAMES: Dict[str, Dict[str, Any]] = {}


def get_index():
    global _players, _team_names
    if _players is None:
        data_root = os.environ.get("SUPERLIG_DATA", DEFAULT_DATA)
        _players, _team_names = load_or_build_index(data_root)
    return _players, _team_names


def _criterion_dict(c: Criterion) -> dict:
    return {"kind": c.kind.value, "label": c.label}


def _serialize_client(grid) -> dict:
    return {
        "mode": grid.mode,
        "difficulty": grid.difficulty,
        "rows": [_criterion_dict(c) for c in grid.rows],
        "cols": [_criterion_dict(c) for c in grid.cols],
        "cells": [
            [{"pool_size": len(grid.cells[i][j].valid_ids)} for j in range(3)]
            for i in range(3)
        ],
    }


def _match_in_pool(
    players: Dict[int, PlayerRecord], pool: Set[int], guess: str
) -> Optional[int]:
    if not (guess or "").strip():
        return None
    best: List[tuple] = []
    for pid in pool:
        r = players[pid]
        for nm in (r.name, r.short_name):
            if not nm:
                continue
            if matches_name_query(nm, guess):
                sc = best_match_score(nm, guess)
                best.append((sc, pid))
    if not best:
        return None
    best.sort(key=lambda x: (-x[0], x[1]))
    return best[0][1]


def _position_hint_label(code: Optional[str]) -> str:
    if not code:
        return ""
    m = {
        "G": "Kaleci",
        "D": "Defans",
        "M": "Orta saha",
        "F": "Forvet",
    }
    return m.get(code, code)


@football_grid_bp.route("/")
def index():
    return render_template("grid.html")


@football_grid_bp.route("/api/new-game", methods=["POST"])
def new_game():
    body = request.get_json(force=True, silent=True) or {}
    difficulty = body.get("difficulty") or "medium"
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    players, team_names = get_index()
    grid = try_generate(players, team_names, difficulty=difficulty)
    if not grid:
        return (
            jsonify(
                {
                    "error": "Bu zorluk için uygun oyun üretilemedi. Başka seviye deneyin veya tekrar deneyin."
                }
            ),
            400,
        )

    gid = str(uuid.uuid4())
    cells_data: List[List[dict]] = []
    for i in range(3):
        row = []
        for j in range(3):
            c = grid.cells[i][j]
            row.append(
                {
                    "valid_ids": set(c.valid_ids),
                    "hint_position": c.hint_position,
                    "hint_seasons": c.hint_seasons,
                    "hints_texts": [],
                    "solved": False,
                    "solved_player_id": None,
                }
            )
        cells_data.append(row)

    GAMES[gid] = {
        "cells": cells_data,
        "used_players": set(),
    }
    payload = _serialize_client(grid)
    payload["game_id"] = gid
    return jsonify(payload)


@football_grid_bp.route("/api/suggest", methods=["POST"])
def suggest():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    ri, ci = body.get("row"), body.get("col")
    q = body.get("q", "")
    if gid not in GAMES or ri is None or ci is None:
        return jsonify({"suggestions": []})
    try:
        ri, ci = int(ri), int(ci)
    except (TypeError, ValueError):
        return jsonify({"suggestions": []})
    if not (0 <= ri < 3 and 0 <= ci < 3):
        return jsonify({"suggestions": []})

    players, _ = get_index()
    st = GAMES[gid]
    cell = st["cells"][ri][ci]
    if cell["solved"]:
        return jsonify({"suggestions": []})

    q = (q or "").strip()
    if len(q) < SUGGEST_MIN_CHARS:
        return jsonify({"suggestions": []})

    rows_out: List[tuple] = []
    for pid, r in players.items():
        name = r.name or r.short_name
        if not name:
            continue
        if not matches_name_query(name, q):
            continue
        sc = best_match_score(name, q)
        rows_out.append((-sc, name.lower(), name, pid))

    rows_out.sort(key=lambda x: (x[0], x[2]))
    out = [{"id": p, "name": n} for _, _, n, p in rows_out[:14]]
    return jsonify({"suggestions": out})


@football_grid_bp.route("/api/guess", methods=["POST"])
def guess():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    ri, ci = body.get("row"), body.get("col")
    name = body.get("name", "")
    if gid not in GAMES or ri is None or ci is None:
        return jsonify({"ok": False, "error": "Oyun bulunamadı."}), 400
    try:
        ri, ci = int(ri), int(ci)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Geçersiz hücre."}), 400
    if not (0 <= ri < 3 and 0 <= ci < 3):
        return jsonify({"ok": False, "error": "Geçersiz hücre."}), 400

    players, _ = get_index()
    st = GAMES[gid]
    cell = st["cells"][ri][ci]
    if cell["solved"]:
        return jsonify({"ok": False, "error": "Bu kutu zaten dolduruldu."})

    pool = cell["valid_ids"]
    pid = _match_in_pool(players, pool, name)
    if pid is None:
        return jsonify({"ok": False, "error": "Bu arama ile eşleşen oyuncu yok veya kutu için geçersiz."})

    if pid in st["used_players"]:
        return jsonify({"ok": False, "error": "Bu oyuncu başka bir kutuda kullanıldı."})

    cell["solved"] = True
    cell["solved_player_id"] = pid
    st["used_players"].add(pid)
    r = players[pid]
    return jsonify(
        {
            "ok": True,
            "player": {"id": pid, "name": r.name or r.short_name},
        }
    )


@football_grid_bp.route("/api/hint", methods=["POST"])
def hint():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    ri, ci = body.get("row"), body.get("col")
    if gid not in GAMES or ri is None or ci is None:
        return jsonify({"error": "Oyun bulunamadı."}), 400
    ri, ci = int(ri), int(ci)
    st = GAMES[gid]
    cell = st["cells"][ri][ci]
    if cell["solved"]:
        return jsonify({"error": "Kutu zaten çözüldü."}), 400

    pos = cell["hint_position"]
    seasons = cell["hint_seasons"]
    texts: List[str] = cell.setdefault("hints_texts", [])
    n = len(texts)

    if n == 0:
        if pos:
            text = f"Pozisyon: {_position_hint_label(pos)}"
        else:
            text = f"Süper Lig’de {seasons} farklı sezonda kadroda yer aldı."
        texts.append(text)
        return jsonify({"hints": list(texts), "latest": text})

    if n == 1 and pos:
        text = f"Süper Lig’de {seasons} farklı sezonda kadroda yer aldı."
        texts.append(text)
        return jsonify({"hints": list(texts), "latest": text})

    return jsonify({"error": "Bu kutu için başka ipucu yok."}), 400


@football_grid_bp.route("/api/hint-list", methods=["POST"])
def hint_list():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    ri, ci = body.get("row"), body.get("col")
    if gid not in GAMES or ri is None or ci is None:
        return jsonify({"hints": []})
    try:
        ri, ci = int(ri), int(ci)
    except (TypeError, ValueError):
        return jsonify({"hints": []})
    if not (0 <= ri < 3 and 0 <= ci < 3):
        return jsonify({"hints": []})
    cell = GAMES[gid]["cells"][ri][ci]
    return jsonify({"hints": list(cell.get("hints_texts", []))})


def create_standalone_app() -> Flask:
    """Local dev: python app.py"""
    application = Flask(__name__)
    application.config["JSON_AS_ASCII"] = False
    application.register_blueprint(football_grid_bp, url_prefix="")
    return application


app = create_standalone_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=True)
