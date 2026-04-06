"""
Build 11-12/player_stats.csv from FBref-style regular-season rows + SofaScore player_ids.

Source: ../archive/11-12_tff/fbref_regular_season_1112.csv (columns below).
Scope: regular season only (34 matches for most players; top 8 still 34 here — playoff NOT included).

Unmatched rows -> ../archive/11-12_tff/fbref_1112_unmatched.csv

Usage (from repo root or this folder):
  python build_1112_player_stats_from_fbref.py
"""

from __future__ import annotations

import csv
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

SEASON_ID = 3831

ROOT = Path(__file__).resolve().parent.parent
SEASON_DIR = ROOT / "11-12"
TFF_ARTIFACT_DIR = ROOT / "archive" / "11-12_tff"
SRC = TFF_ARTIFACT_DIR / "fbref_regular_season_1112.csv"
OUT = SEASON_DIR / "player_stats.csv"
UNRES = TFF_ARTIFACT_DIR / "fbref_1112_unmatched.csv"
PROF = SEASON_DIR / "player_profiles.csv"

SQUAD_TO_TEAM_ID: dict[str, int] = {
    "galatasaray": 3061,
    "fenerbahçe": 3052,
    "fenerbahce": 3052,
    "trabzonspor": 3051,
    "beşiktaş": 3050,
    "besiktas": 3050,
    "beşiktaş jk": 3050,
    "besiktas jk": 3050,
    "bursaspor": 3055,
    "eskişehirspor": 6364,
    "eskisehirspor": 6364,
    "istanbul bb": 3086,
    "i̇stanbul bb": 3086,
    "başakşehir fk": 3086,
    "basaksehir fk": 3086,
    "sivasspor": 3076,
    "gençlerbirliği": 7802,
    "genclerbirligi": 7802,
    "gaziantepspor": 3060,
    "kayserispor": 3072,
    "karabükspor": 7027,
    "karabukspor": 7027,
    "mersin i̇y": 3102,
    "mersin iy": 3102,
    "mersin i̇dman yurdu": 3102,
    "mersin idman yurdu": 3102,
    "orduspor": 5140,
    "antalyaspor": 3056,
    "samsunspor": 3053,
    "manisaspor": 3100,
    "ankaragücü": 3103,
    "ankaragucu": 3103,
    "mke ankara gücü": 3103,
    "mke ankara gucu": 3103,
}

# FBref display -> tokens we also search in normalized profile names
NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "alex de souza": ("alex",),
    "sidney cristiano dos santos (tita)": ("tita", "sidney"),
    "sidney c. d. santos (tita)": ("tita",),
    # _norm_key strips (...); keep base so "Tita" is still a needle
    "sidney cristiano dos santos": ("tita", "sidney"),
    "beckham": ("bebé", "bebe"),
    "guti": ("guti",),
    "dedê": ("dede",),
    "kahê": ("kahe",),
    "tom": ("tom",),
    "jerry akaminko": ("jerry akaminko",),
    "danilo bueno": ("danilo petrolli bueno", "petrolli"),
    "yigit gokoglan": ("yigit ismail gokoglan", "gokoglan"),
    "theo lewis weeks": ("theo weeks",),
    "marcio nobre": ("mert nobre", "nobre"),
    "joao da rocha ribeiro": ("joao ribeiro", "ribeiro"),
    "kagan timurcin konuk": ("kaan kilci", "kilci"),
    "herve tum": ("herve germain tum", "germain"),
    "mehmet yilmaz": ("mehmet hilmi yilmaz", "hilmi"),
    "abdullah elyasa sume": ("elyasa sume", "elyasa"),
}


def _squash(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("İ", "I").replace("ı", "i")
    return s.lower().strip()


def _norm_key(s: str) -> str:
    s = _squash(s)
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _team_id_from_squad(raw: str) -> int | None:
    k = _norm_key(raw)
    return SQUAD_TO_TEAM_ID.get(k)


def load_profiles_by_team() -> dict[int, list[tuple[int, str, str]]]:
    """team_id -> [(player_id, name, short_name)] deduped by player_id."""
    by_team: dict[int, dict[int, tuple[int, str, str]]] = {}
    with open(PROF, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                pid = int(row["player_id"])
                tid = int(row["team_id"])
            except (KeyError, ValueError):
                continue
            name = (row.get("name") or "").strip()
            short = (row.get("short_name") or "").strip()
            by_team.setdefault(tid, {})[pid] = (pid, name, short)
    return {tid: list(m.values()) for tid, m in by_team.items()}


def _best_pid(
    team_id: int,
    fb_name: str,
    roster: dict[int, list[tuple[int, str, str]]],
) -> tuple[int | None, float, str]:
    nk = _norm_key(fb_name)
    needles = [nk]
    if nk in NAME_ALIASES:
        needles.extend(_norm_key(x) for x in NAME_ALIASES[nk])
    cands = roster.get(team_id, [])
    best: tuple[int | None, float, str] = (None, 0.0, "")
    for pid, nm, sn in cands:
        blob = _norm_key(f"{nm} {sn}")
        r = 0.0
        for nd in needles:
            if nd == blob or (len(nd) >= 3 and nd in blob):
                r = max(r, 1.0)
            else:
                r = max(r, SequenceMatcher(None, nd, blob).ratio())
        if r > best[1]:
            best = (pid, r, f"{nm} / {sn}")
    return best


def main() -> None:
    roster = load_profiles_by_team()
    stats_header = [
        "player_id",
        "team_id",
        "season_id",
        "appearances",
        "matches_started",
        "minutes_played",
        "goals",
        "assists",
        "expected_goals",
        "expected_assists",
        "yellow_cards",
        "red_cards",
        "rating",
        "total_shots",
        "shots_on_target",
        "accurate_passes",
        "total_passes",
        "accurate_passes_pct",
        "key_passes",
        "tackles",
        "interceptions",
        "successful_dribbles",
        "ground_duels_won_pct",
        "aerial_duels_won_pct",
        "saves",
        "clean_sheets",
        "goals_conceded",
        "big_chances_created",
        "big_chances_missed",
    ]
    out_rows: list[dict[str, str]] = []
    bad: list[dict[str, str]] = []

    with open(SRC, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pname = (row.get("player_name") or "").strip()
            squad = (row.get("squad") or "").strip()
            if not pname or not squad:
                continue
            tid = _team_id_from_squad(squad)
            if tid is None:
                bad.append({**row, "_reason": f"unknown_squad:{squad}"})
                continue
            pid, score, prof = _best_pid(tid, pname, roster)
            if pid is None or score < 0.65:
                bad.append(
                    {
                        **row,
                        "_reason": f"no_match:{score:.2f}:{prof}",
                    }
                )
                continue
            out_rows.append(
                {
                    "player_id": str(pid),
                    "team_id": str(tid),
                    "season_id": str(SEASON_ID),
                    "appearances": str(int(row["appearances"])),
                    "matches_started": str(int(row["matches_started"])),
                    "minutes_played": str(int(row["minutes_played"])),
                    "goals": str(int(row["goals"])),
                    "assists": str(int(row["assists"])),
                    "expected_goals": "",
                    "expected_assists": "",
                    "yellow_cards": str(int(row.get("yellow_cards") or 0)),
                    "red_cards": str(int(row.get("red_cards") or 0)),
                    "rating": "",
                    "total_shots": "",
                    "shots_on_target": "",
                    "accurate_passes": "",
                    "total_passes": "",
                    "accurate_passes_pct": "",
                    "key_passes": "",
                    "tackles": "",
                    "interceptions": "",
                    "successful_dribbles": "",
                    "ground_duels_won_pct": "",
                    "aerial_duels_won_pct": "",
                    "saves": "",
                    "clean_sheets": "",
                    "goals_conceded": "",
                    "big_chances_created": "",
                    "big_chances_missed": "",
                }
            )

    out_rows.sort(key=lambda r: (int(r["team_id"]), int(r["player_id"])))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=stats_header)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    with open(UNRES, "w", encoding="utf-8", newline="") as f:
        if bad:
            wf = csv.DictWriter(f, fieldnames=list(bad[0].keys()))
            wf.writeheader()
            wf.writerows(bad)

    print(f"Wrote {len(out_rows)} rows -> {OUT}")
    print(f"Unresolved {len(bad)} -> {UNRES}")


if __name__ == "__main__":
    main()
