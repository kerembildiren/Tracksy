"""
Flask server for the Süper Lig grid game.
Can run standalone or register as blueprint on HarmanGames (url_prefix /sportsguesser/football).
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from flask import Blueprint, Flask, jsonify, render_template, request

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from player_index import PlayerRecord, load_or_build_index
from generator import try_generate, Criterion
from search_util import format_suggestion_list, matches_name_query, best_match_score

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

WIN_LINES: List[List[Tuple[int, int]]] = [
    [(0, 0), (0, 1), (0, 2)],
    [(1, 0), (1, 1), (1, 2)],
    [(2, 0), (2, 1), (2, 2)],
    [(0, 0), (1, 0), (2, 0)],
    [(0, 1), (1, 1), (2, 1)],
    [(0, 2), (1, 2), (2, 2)],
    [(0, 0), (1, 1), (2, 2)],
    [(0, 2), (1, 1), (2, 0)],
]

HINTS_PER_PLAYER = 4
MAX_HINT_PLAYERS = 12


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


def _hint_queue(players: Dict[int, PlayerRecord], pool: Set[int]) -> List[int]:
    ranked: List[Tuple[int, str, int]] = []
    for pid in pool:
        r = players[pid]
        nm = r.name or r.short_name or str(pid)
        ranked.append((r.season_count, nm, pid))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    out: List[int] = []
    seen: Set[int] = set()
    for _, _, pid in ranked:
        if pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
        if len(out) >= MAX_HINT_PLAYERS:
            break
    return out


def _top_team_seasons(r: PlayerRecord) -> Tuple[Optional[int], int]:
    if not r.team_seasons:
        return None, 0
    ranked = [(len(s), tid) for tid, s in r.team_seasons.items()]
    ranked.sort(key=lambda x: (-x[0], x[1]))
    n, tid = ranked[0]
    return tid, n


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


def _hint_state(cell: dict) -> dict:
    return {
        "hint_focus": cell["hint_focus"],
        "hint_queue_length": len(cell["hint_queue"]),
        "pages": [list(x) for x in cell["hints_per_player"]],
    }


def _versus_winner(cells: List[List[dict]]) -> Optional[int]:
    for line in WIN_LINES:
        marks = [cells[r][c].get("mark") for r, c in line]
        if marks == ["X", "X", "X"]:
            return 1
        if marks == ["O", "O", "O"]:
            return 2
    return None


def _board_full(cells: List[List[dict]]) -> bool:
    return all(cells[i][j]["solved"] for i in range(3) for j in range(3))


def _game_locked(st: Dict[str, Any]) -> bool:
    if st.get("play_mode") != "versus":
        return False
    if st.get("winner") is not None:
        return True
    return _board_full(st["cells"]) and _versus_winner(st["cells"]) is None


@football_grid_bp.route("/")
def index():
    return render_template("grid.html")


@football_grid_bp.route("/api/new-game", methods=["POST"])
def new_game():
    body = request.get_json(force=True, silent=True) or {}
    difficulty = body.get("difficulty") or "medium"
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    play_mode = body.get("play_mode") or "solo"
    if play_mode not in ("solo", "versus"):
        play_mode = "solo"

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
            hq = _hint_queue(players, set(c.valid_ids))
            row.append(
                {
                    "valid_ids": set(c.valid_ids),
                    "hint_queue": hq,
                    "hint_focus": 0,
                    "hints_per_player": [[] for _ in hq],
                    "solved": False,
                    "solved_player_id": None,
                    "mark": None,
                }
            )
        cells_data.append(row)

    GAMES[gid] = {
        "cells": cells_data,
        "used_players": set(),
        "play_mode": play_mode,
        "current_turn": 1 if play_mode == "versus" else None,
        "winner": None,
    }
    payload = _serialize_client(grid)
    payload["game_id"] = gid
    payload["play_mode"] = play_mode
    payload["current_turn"] = GAMES[gid]["current_turn"]
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
    if _game_locked(st):
        return jsonify({"suggestions": []})
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
    out = format_suggestion_list(
        rows_out,
        limit=14,
        nationality_for=lambda pid: players[pid].primary_nationality(),
    )
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
    cells = st["cells"]
    cell = cells[ri][ci]
    play_mode = st.get("play_mode", "solo")

    if play_mode == "versus":
        if st.get("winner") is not None:
            return jsonify({"ok": False, "error": "Oyun bitti."}), 400
        if _board_full(cells) and _versus_winner(cells) is None:
            return jsonify({"ok": False, "error": "Oyun bitti (berabere)."}), 400

    if cell["solved"]:
        return jsonify({"ok": False, "error": "Bu kutu zaten dolduruldu."})

    pool = cell["valid_ids"]
    pid = _match_in_pool(players, pool, name)

    if play_mode == "versus":
        turn = int(st["current_turn"] or 1)
        bad = (
            pid is None
            or pid not in pool
            or (pid in st["used_players"])
        )
        if bad:
            next_turn = 2 if turn == 1 else 1
            st["current_turn"] = next_turn
            err = "Eşleşen oyuncu yok, havuz dışı veya zaten kullanıldı."
            if pid is not None and pid in st["used_players"]:
                err = "Bu oyuncu başka bir kutuda kullanıldı."
            elif pid is None:
                err = "Bu arama ile eşleşen oyuncu yok veya kutu için geçersiz."
            return jsonify(
                {
                    "ok": False,
                    "wrong": True,
                    "pass_turn": True,
                    "error": err,
                    "current_turn": next_turn,
                }
            )

        mark = "X" if turn == 1 else "O"
        cell["solved"] = True
        cell["solved_player_id"] = pid
        cell["mark"] = mark
        st["used_players"].add(pid)
        w = _versus_winner(cells)
        if w is not None:
            st["winner"] = w
        elif _board_full(cells):
            st["winner"] = 0
        next_turn = 2 if turn == 1 else 1
        st["current_turn"] = next_turn
        r = players[pid]
        return jsonify(
            {
                "ok": True,
                "play_mode": "versus",
                "mark": mark,
                "current_turn": next_turn,
                "winner": st.get("winner"),
                "player": {"id": pid, "name": r.name or r.short_name},
            }
        )

    # solo
    if pid is None:
        return jsonify(
            {"ok": False, "error": "Bu arama ile eşleşen oyuncu yok veya kutu için geçersiz."}
        )
    if pid in st["used_players"]:
        return jsonify({"ok": False, "error": "Bu oyuncu başka bir kutuda kullanıldı."})

    cell["solved"] = True
    cell["solved_player_id"] = pid
    st["used_players"].add(pid)
    r = players[pid]
    return jsonify(
        {
            "ok": True,
            "play_mode": "solo",
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
    players, team_names = get_index()
    st = GAMES[gid]
    cell = st["cells"][ri][ci]
    if cell["solved"]:
        return jsonify({"error": "Kutu zaten çözüldü."}), 400

    queue: List[int] = cell["hint_queue"]
    if not queue:
        return jsonify({"error": "Bu kutu için ipucu yok."}), 400
    focus = int(cell["hint_focus"])
    if focus < 0 or focus >= len(queue):
        focus = 0
        cell["hint_focus"] = focus
    per: List[List[str]] = cell["hints_per_player"]
    hints = per[focus]
    if len(hints) >= HINTS_PER_PLAYER:
        return jsonify({"error": "Bu oyuncu için tüm ipuçları alındı."}), 400

    pid = queue[focus]
    r = players[pid]
    n = len(hints)
    if n == 0:
        pos = r.primary_position()
        if pos:
            text = f"Pozisyon: {_position_hint_label(pos)}"
        else:
            text = "Pozisyon: bilinmiyor"
    elif n == 1:
        text = f"Süper Lig’de {r.season_count} farklı sezonda kadroda yer aldı."
    elif n == 2:
        nat = r.primary_nationality()
        text = f"Uyruk: {nat}" if nat else "Uyruk: missing"
    else:
        tid, cnt = _top_team_seasons(r)
        if tid is None or cnt == 0:
            text = "En çok oynadığı takım: veri yok"
        else:
            tname = team_names.get(tid) or f"Kulüp #{tid}"
            text = f"En çok oynadığı takım: {tname} ({cnt} sezon)"

    hints.append(text)
    hs = _hint_state(cell)
    focus_done = len(hints) >= HINTS_PER_PLAYER
    can_switch = focus_done and len(queue) > 1
    return jsonify(
        {
            "latest": text,
            **hs,
            "focus_hints_complete": focus_done,
            "can_switch_player": can_switch,
        }
    )


@football_grid_bp.route("/api/hint-focus", methods=["POST"])
def hint_focus():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    ri, ci = body.get("row"), body.get("col")
    if gid not in GAMES or ri is None or ci is None:
        return jsonify({"error": "Oyun bulunamadı."}), 400
    try:
        ri, ci = int(ri), int(ci)
        focus = int(body.get("focus"))
    except (TypeError, ValueError):
        return jsonify({"error": "Geçersiz parametre."}), 400
    cell = GAMES[gid]["cells"][ri][ci]
    n = len(cell["hint_queue"])
    if n == 0:
        return jsonify({"error": "İpucu sırası yok."}), 400
    focus = max(0, min(focus, n - 1))
    cell["hint_focus"] = focus
    per = cell["hints_per_player"][focus]
    return jsonify(
        {
            **_hint_state(cell),
            "focus_hints_complete": len(per) >= HINTS_PER_PLAYER,
            "can_switch_player": len(per) >= HINTS_PER_PLAYER and n > 1,
        }
    )


@football_grid_bp.route("/api/hint-list", methods=["POST"])
def hint_list():
    body = request.get_json(force=True, silent=True) or {}
    gid = body.get("game_id")
    ri, ci = body.get("row"), body.get("col")
    if gid not in GAMES or ri is None or ci is None:
        return jsonify({"hints": [], "hint_focus": 0, "hint_queue_length": 0, "pages": []})
    try:
        ri, ci = int(ri), int(ci)
    except (TypeError, ValueError):
        return jsonify({"hints": [], "hint_focus": 0, "hint_queue_length": 0, "pages": []})
    if not (0 <= ri < 3 and 0 <= ci < 3):
        return jsonify({"hints": [], "hint_focus": 0, "hint_queue_length": 0, "pages": []})
    cell = GAMES[gid]["cells"][ri][ci]
    hs = _hint_state(cell)
    f = int(cell["hint_focus"])
    cur = cell["hints_per_player"][f] if cell["hints_per_player"] else []
    return jsonify(
        {
            "hints": list(cur),
            **hs,
            "focus_hints_complete": len(cur) >= HINTS_PER_PLAYER,
            "can_switch_player": len(cur) >= HINTS_PER_PLAYER
            and len(cell["hint_queue"]) > 1,
        }
    )


def create_standalone_app() -> Flask:
    """Local dev: python app.py"""
    application = Flask(__name__)
    application.config["JSON_AS_ASCII"] = False
    application.register_blueprint(football_grid_bp, url_prefix="")
    return application


app = create_standalone_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=True)
