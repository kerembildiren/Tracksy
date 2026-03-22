"""
FB–GS–BJK–TS derbi maçları: matches.csv taraması + goals/cards/subs yüklemesi.

Çalışma zamanında oyun varsayılan olarak bundled/derbies.json kullanır (build_derby_bundle.py).
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List, Optional

# Beşiktaş, Trabzonspor, Fenerbahçe, Galatasaray
DERBI_TEAM_IDS = frozenset({3050, 3051, 3052, 3061})

# 01-02 … 24-25 (dataset klasörleri)
SEASON_KEYS = [f"{y:02d}-{(y + 1) % 100:02d}" for y in range(1, 25)]


def season_label(season_key: str) -> str:
    a, _ = season_key.split("-")
    y1 = 2000 + int(a)
    return f"{y1}/{y1 + 1}"


def _is_derby_row(hid: int, aid: int) -> bool:
    return hid in DERBI_TEAM_IDS and aid in DERBI_TEAM_IDS and hid != aid


def build_derby_index(data_root: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for sk in SEASON_KEYS:
        path = os.path.join(data_root, sk, "matches.csv")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    hid = int(row["home_team_id"])
                    aid = int(row["away_team_id"])
                except (KeyError, ValueError):
                    continue
                if not _is_derby_row(hid, aid):
                    continue
                try:
                    mid = int(row["match_id"])
                    rnd = int(row["round"])
                except (KeyError, ValueError):
                    continue
                st = (row.get("status_code") or "").strip()
                if st and st != "100":
                    continue
                out.append(
                    {
                        "season_key": sk,
                        "match_id": mid,
                        "round": rnd,
                        "home_team": (row.get("home_team") or "").strip(),
                        "away_team": (row.get("away_team") or "").strip(),
                        "home_team_id": hid,
                        "away_team_id": aid,
                    }
                )
    return out


def _read_csv_filtered(
    folder: str, filename: str, match_id: int
) -> List[Dict[str, str]]:
    path = os.path.join(folder, filename)
    if not os.path.isfile(path):
        return []
    mid = str(match_id)
    rows: List[Dict[str, str]] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("match_id") == mid:
                rows.append(dict(row))
    return rows


def load_match_truth(data_root: str, season_key: str, match_id: int) -> Dict[str, Any]:
    folder = os.path.join(data_root, season_key)
    mpath = os.path.join(folder, "matches.csv")
    base: Dict[str, Any] = {
        "match_id": match_id,
        "season_key": season_key,
        "season_label": season_label(season_key),
        "round": 0,
        "home_team": "",
        "away_team": "",
        "home_team_id": 0,
        "away_team_id": 0,
        "home_score": 0,
        "away_score": 0,
        "goals": [],
        "cards": [],
        "subs": [],
    }
    if not os.path.isfile(mpath):
        return base
    mid = str(match_id)
    with open(mpath, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("match_id") != mid:
                continue
            base["round"] = int(row.get("round") or 0)
            base["home_team"] = (row.get("home_team") or "").strip()
            base["away_team"] = (row.get("away_team") or "").strip()
            base["home_team_id"] = int(row["home_team_id"])
            base["away_team_id"] = int(row["away_team_id"])
            base["home_score"] = int(row.get("home_score") or 0)
            base["away_score"] = int(row.get("away_score") or 0)
            break

    for g in _read_csv_filtered(folder, "goals.csv", match_id):
        try:
            minute = int(g.get("minute") or -1)
        except ValueError:
            minute = -1
        if minute < 0:
            continue
        at = (g.get("added_time") or "").strip()
        added = int(at) if at.isdigit() else None
        base["goals"].append(
            {
                "minute": minute,
                "added_time": added,
                "scorer": (g.get("scorer") or "").strip(),
                "scorer_id": int(g["scorer_id"]) if g.get("scorer_id") else 0,
                "is_home": (g.get("is_home") or "").lower() in ("true", "1"),
            }
        )

    for c in _read_csv_filtered(folder, "cards.csv", match_id):
        try:
            minute = int(c.get("minute") or -99)
        except ValueError:
            minute = -99
        if minute < 0:
            continue
        pl = (c.get("player") or "").strip()
        if not pl:
            continue
        at = (c.get("added_time") or "").strip()
        added = int(at) if at.isdigit() else None
        base["cards"].append(
            {
                "minute": minute,
                "added_time": added,
                "player": pl,
                "player_id": int(c["player_id"]) if c.get("player_id") else 0,
                "card_type": (c.get("card_type") or "yellow").strip(),
                "is_home": (c.get("is_home") or "").lower() in ("true", "1"),
            }
        )

    for s in _read_csv_filtered(folder, "substitutions.csv", match_id):
        try:
            minute = int(s.get("minute") or -1)
        except ValueError:
            minute = -1
        if minute < 0:
            continue
        pin = (s.get("player_in") or "").strip()
        pout = (s.get("player_out") or "").strip()
        if not pin and not pout:
            continue
        base["subs"].append(
            {
                "minute": minute,
                "player_in": pin,
                "player_in_id": int(s["player_in_id"]) if s.get("player_in_id") else 0,
                "player_out": pout,
                "player_out_id": int(s["player_out_id"]) if s.get("player_out_id") else 0,
                "is_home": (s.get("is_home") or "").lower() in ("true", "1"),
            }
        )

    return base


def public_challenge_payload(truth: Dict[str, Any]) -> Dict[str, Any]:
    goals = []
    for i, g in enumerate(truth["goals"]):
        goals.append(
            {
                "idx": i,
                "minute": g["minute"],
                "added_time": g.get("added_time"),
                "is_home": g["is_home"],
            }
        )
    cards = []
    for i, c in enumerate(truth["cards"]):
        cards.append(
            {
                "idx": i,
                "minute": c["minute"],
                "added_time": c.get("added_time"),
                "card_type": c["card_type"],
                "is_home": c["is_home"],
            }
        )
    subs = []
    for i, s in enumerate(truth["subs"]):
        subs.append({"idx": i, "minute": s["minute"], "is_home": s["is_home"]})
    return {
        "season_label": truth["season_label"],
        "round": truth["round"],
        "home_team": truth["home_team"],
        "away_team": truth["away_team"],
        "home_team_id": truth["home_team_id"],
        "away_team_id": truth["away_team_id"],
        "goals": goals,
        "cards": cards,
        "subs": subs,
        "has_score": True,
        "n_goals": len(goals),
        "n_cards": len(cards),
        "n_subs": len(subs),
    }


def default_bundle_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "bundled", "derbies.json")


def load_derby_bundle(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """bundled/derbies.json içindeki tam maç kayıtları (skor, gol, kart, oyuncu değişikliği)."""
    p = os.path.abspath(path or os.environ.get("DERBY_BUNDLE_JSON") or default_bundle_path())
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        doc = json.load(f)
    matches = doc.get("matches")
    if not isinstance(matches, list):
        return []
    return [m for m in matches if isinstance(m, dict) and m.get("home_team")]
