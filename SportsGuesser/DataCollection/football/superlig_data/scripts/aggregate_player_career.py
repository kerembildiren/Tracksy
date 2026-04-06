"""Aggregate Süper Lig stats per player across superlig_data (all seasons)."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (player_id, display name)
PLAYERS = [
    (12863, "Alex (de Souza)"),
    (60637, "Oktay Delibalta"),
]


def main() -> None:
    seasons = sorted(
        d.name
        for d in ROOT.iterdir()
        if d.is_dir() and len(d.name) == 5 and d.name[2] == "-"
    )

    for pid, label in PLAYERS:
        print("=" * 60)
        print(f"{label}  player_id={pid}")
        print("=" * 60)

        career_stats: dict | None = None
        career_goals = 0
        career_assists = 0
        career_yellow = 0
        career_red = 0
        by_season: dict[str, dict] = {}

        for sk in seasons:
            folder = ROOT / sk
            sd = by_season[sk] = {
                "player_stats": None,
                "goals": 0,
                "assists": 0,
                "yellow": 0,
                "red": 0,
            }

            ps_path = folder / "player_stats.csv"
            if ps_path.is_file():
                with open(ps_path, encoding="utf-8", newline="") as f:
                    for row in csv.DictReader(f):
                        if int(row["player_id"]) != pid:
                            continue
                        rec = {
                            "team_id": row["team_id"],
                            "appearances": int(float(row.get("appearances") or 0)),
                            "starts": int(float(row.get("matches_started") or 0)),
                            "minutes": int(float(row.get("minutes_played") or 0)),
                            "goals": int(float(row.get("goals") or 0)),
                            "assists": int(float(row.get("assists") or 0)),
                            "yellow": int(float(row.get("yellow_cards") or 0)),
                            "red": int(float(row.get("red_cards") or 0)),
                        }
                        sd["player_stats"] = rec
                        if career_stats is None:
                            career_stats = {**rec, "team_ids": [rec["team_id"]]}
                        else:
                            career_stats["appearances"] += rec["appearances"]
                            career_stats["starts"] += rec["starts"]
                            career_stats["minutes"] += rec["minutes"]
                            career_stats["goals"] += rec["goals"]
                            career_stats["assists"] += rec["assists"]
                            career_stats["yellow"] += rec["yellow"]
                            career_stats["red"] += rec["red"]
                            if rec["team_id"] not in career_stats["team_ids"]:
                                career_stats["team_ids"].append(rec["team_id"])
                        break

            g_path = folder / "goals.csv"
            if g_path.is_file():
                with open(g_path, encoding="utf-8", newline="") as f:
                    for row in csv.DictReader(f):
                        if row.get("scorer_id") and str(row["scorer_id"]).strip().isdigit():
                            if int(row["scorer_id"]) == pid:
                                sd["goals"] += 1
                                career_goals += 1
                        aid = row.get("assist_id") or ""
                        if aid.strip().isdigit() and int(aid) == pid:
                            sd["assists"] += 1
                            career_assists += 1

            c_path = folder / "cards.csv"
            if c_path.is_file():
                with open(c_path, encoding="utf-8", newline="") as f:
                    for row in csv.DictReader(f):
                        if not row.get("player_id"):
                            continue
                        try:
                            if int(row["player_id"]) != pid:
                                continue
                        except ValueError:
                            continue
                        ct = (row.get("card_type") or "").lower()
                        if ct == "red":
                            sd["red"] += 1
                            career_red += 1
                        else:
                            sd["yellow"] += 1
                            career_yellow += 1

        print("\nPer season:")
        for sk in seasons:
            sd = by_season[sk]
            if (
                sd["player_stats"] is None
                and sd["goals"] == 0
                and sd["assists"] == 0
                and sd["yellow"] == 0
                and sd["red"] == 0
            ):
                continue
            parts = [sk]
            ps = sd["player_stats"]
            if ps:
                parts.append(
                    f"stats: app {ps['appearances']} st {ps['starts']} min {ps['minutes']} "
                    f"G {ps['goals']} A {ps['assists']} YC {ps['yellow']} RC {ps['red']} (team {ps['team_id']})"
                )
            ev = []
            if sd["goals"] or sd["assists"]:
                ev.append(f"goals.csv G {sd['goals']} A {sd['assists']}")
            if sd["yellow"] or sd["red"]:
                ev.append(f"cards YC {sd['yellow']} RC {sd['red']}")
            if ev:
                parts.append(" · ".join(ev))
            print("  " + " | ".join(parts))

        print("\nCareer from player_stats.csv only (sum of rows):")
        if career_stats:
            cs = career_stats
            print(
                f"  apps {cs['appearances']}, starts {cs['starts']}, min {cs['minutes']}, "
                f"G {cs['goals']}, A {cs['assists']}, YC {cs['yellow']}, RC {cs['red']}"
            )
        else:
            print("  (no player_stats rows)")

        print("\nCareer from event files (goals.csv + cards.csv), all seasons:")
        print(
            f"  goals scored: {career_goals} | assists (assist_id): {career_assists} | "
            f"yellow: {career_yellow} | red: {career_red}"
        )
        print()


if __name__ == "__main__":
    main()
