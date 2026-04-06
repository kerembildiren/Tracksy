"""
Build standard goals.csv for 2011-12 from TFF exports + SofaScore match_ids.

Reads:
  ../archive/11-12_tff/tff_match_index.csv, tff_goals_by_match.csv, tff_gol_kralligi.csv
  ../11-12/matches.csv, ../11-12/player_profiles.csv
  ../tff_mappings/kulup_to_team_id_1112.csv

Fetches once: TFF archive pageID=1139 for macId -> round (disambiguation).

Writes:
  ../11-12/goals.csv (replaces)
  ../archive/11-12_tff/tff_mac_to_match_id.csv
  ../archive/11-12_tff/tff_kisi_to_player_id.csv (resolved + unresolved rows)
  ../archive/11-12_tff/tff_merge_report.json
  ../archive/11-12_tff/goals_tff_super_final.csv (if any)
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
SEASON_DIR = ROOT / "11-12"
TFF_ARTIFACT_DIR = ROOT / "archive" / "11-12_tff"
MAPPINGS = ROOT / "tff_mappings" / "kulup_to_team_id_1112.csv"
KISI_OVERRIDES = ROOT / "tff_mappings" / "tff_kisi_to_player_id_overrides.csv"
ARCHIVE_URL = "https://www.tff.org/default.aspx?pageID=1139"
# Spor Toto Süper Final (playoff) — same team/score pairs can repeat the regular season; do not merge into league goals.csv
SUPER_FINAL_TFF_MAC_IDS = frozenset({106083, 106084, 106095, 106096})
ENCODING = "windows-1254"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
)

_TR = str.maketrans(
    {
        "İ": "I",
        "I": "I",
        "ı": "I",
        "Ş": "S",
        "ş": "S",
        "Ğ": "G",
        "ğ": "G",
        "Ü": "U",
        "ü": "U",
        "Ö": "O",
        "ö": "O",
        "Ç": "C",
        "ç": "C",
    }
)


def norm_name(s: str) -> str:
    s = (s or "").translate(_TR).upper()
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_name(a), norm_name(b)).ratio()


def load_kisi_overrides(path: Path) -> dict[int, int]:
    if not path.is_file():
        return {}
    out: dict[int, int] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("tff_kisi_id", "").strip() or row.get("tff_kisi_id", "").startswith("#"):
                continue
            out[int(row["tff_kisi_id"])] = int(row["player_id"])
    return out


def surname_key(norm: str) -> str:
    parts = norm.split()
    return parts[-1] if parts else ""


def load_kulup_map(path: Path) -> dict[int, int]:
    out: dict[int, int] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("tff_kulup_id", "").strip().startswith("#"):
                continue
            out[int(row["tff_kulup_id"])] = int(row["team_id"])
    return out


def parse_mac_rounds(html: str) -> dict[int, int]:
    """macId -> round (1-34) from main league Hafta blocks."""
    rounds: dict[int, int] = {}
    parts = re.split(r"(\d+)\.Hafta", html)
    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        rnd = int(parts[i])
        for mid in re.findall(r"macId=(\d+)", parts[i + 1], flags=re.I):
            rounds[int(mid)] = rnd
    return rounds


def fetch_archive() -> str:
    r = requests.get(ARCHIVE_URL, headers={"User-Agent": USER_AGENT}, timeout=90)
    r.raise_for_status()
    r.encoding = ENCODING
    return r.text


def load_profiles(path: Path) -> tuple[dict[int, dict], list[dict]]:
    by_id: dict[int, dict] = {}
    rows: list[dict] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                pid = int(row["player_id"])
            except (KeyError, ValueError):
                continue
            by_id[pid] = row
            rows.append(row)
    return by_id, rows


def build_player_index(
    profiles: list[dict],
) -> tuple[
    dict[tuple[int, str], list[int]],
    dict[str, list[int]],
    dict[tuple[int, str], list[int]],
]:
    """(team_id, norm_full), norm_full -> ids, (team_id, surname) -> ids."""
    by_team_name: dict[tuple[int, str], list[int]] = defaultdict(list)
    by_name: dict[str, list[int]] = defaultdict(list)
    by_team_surname: dict[tuple[int, str], list[int]] = defaultdict(list)
    for row in profiles:
        try:
            pid = int(row["player_id"])
            tid = int(row["team_id"])
        except (KeyError, ValueError):
            continue
        for key in (row.get("name") or "", row.get("short_name") or ""):
            n = norm_name(key)
            if not n:
                continue
            by_team_name[(tid, n)].append(pid)
            by_name[n].append(pid)
            sn = surname_key(n)
            if len(sn) >= 3:
                by_team_surname[(tid, sn)].append(pid)
    return by_team_name, by_name, by_team_surname


def resolve_player(
    tff_name: str,
    primary_team_id: Optional[int],
    tff_kisi_id: int,
    overrides: dict[int, int],
    by_team_name: dict[tuple[int, str], list[int]],
    by_name: dict[str, list[int]],
    by_team_surname: dict[tuple[int, str], list[int]],
    profiles_by_id: dict[int, dict],
) -> tuple[Optional[int], str]:
    """Returns (player_id, method)."""
    if tff_kisi_id in overrides:
        return overrides[tff_kisi_id], "override_file"

    nn = norm_name(tff_name)
    if not nn:
        return None, "empty_name"

    if primary_team_id is not None:
        # exact bucket
        for (tid, name), ids in by_team_name.items():
            if tid != primary_team_id:
                continue
            if name == nn and ids:
                return ids[0], "exact_team_norm"

        best_pid: Optional[int] = None
        best_r = 0.0
        for (tid, name), ids in by_team_name.items():
            if tid != primary_team_id:
                continue
            for pid in ids:
                r = ratio(tff_name, profiles_by_id[pid].get("name", ""))
                if r > best_r:
                    best_r = r
                    best_pid = pid
        if best_pid is not None and best_r >= 0.86:
            return best_pid, f"fuzzy_team_{best_r:.2f}"

        sn = surname_key(nn)
        if sn and len(sn) >= 3:
            ids = list(
                dict.fromkeys(by_team_surname.get((primary_team_id, sn), []))
            )
            if len(ids) == 1:
                return ids[0], "surname_team_unique"

    # any team: exact norm on full name
    if nn in by_name and len(set(by_name[nn])) == 1:
        return by_name[nn][0], "exact_any_team"

    best_pid = None
    best_r = 0.0
    for row in profiles_by_id.values():
        pid = int(row["player_id"])
        for fld in ("name", "short_name"):
            r = ratio(tff_name, row.get(fld) or "")
            if r > best_r:
                best_r = r
                best_pid = pid
    if best_pid is not None and best_r >= 0.82:
        return best_pid, f"fuzzy_global_{best_r:.2f}"

    return None, "unresolved"


def link_tff_mac_to_match(
    tff_matches: list[dict],
    sofa_matches: list[dict],
    kulup_map: dict[int, int],
    mac_rounds: dict[int, int],
) -> tuple[dict[int, str], list[dict]]:
    """
    Returns:
      mac_id_int -> match_id_str
      issues: list of dicts for logging
    """
    out: dict[int, str] = {}
    issues: list[dict] = []
    sofa_ended = [
        m
        for m in sofa_matches
        if str(m.get("status", "")).strip() == "Ended"
        and str(m.get("home_score", "")).strip()
        and str(m.get("away_score", "")).strip()
    ]
    for tr in tff_matches:
        mid = int(tr["tff_mac_id"])
        if mid in SUPER_FINAL_TFF_MAC_IDS:
            issues.append(
                {
                    "tff_mac_id": mid,
                    "error": "super_final_excluded_from_league_csv",
                }
            )
            continue
        try:
            hk = kulup_map[int(tr["home_kulup_id"])]
            ak = kulup_map[int(tr["away_kulup_id"])]
        except KeyError as e:
            issues.append({"tff_mac_id": mid, "error": f"missing_kulup_map:{e}"})
            continue
        hs, aws = int(tr["home_score"]), int(tr["away_score"])
        rnd = mac_rounds.get(mid)
        candidates = [
            m
            for m in sofa_ended
            if int(m["home_team_id"]) == hk
            and int(m["away_team_id"]) == ak
            and int(m["home_score"]) == hs
            and int(m["away_score"]) == aws
        ]
        if rnd is not None:
            cr = [m for m in candidates if int(m["round"]) == rnd]
            if cr:
                candidates = cr
        if len(candidates) == 1:
            out[mid] = str(candidates[0]["match_id"])
        elif len(candidates) == 0:
            issues.append(
                {
                    "tff_mac_id": mid,
                    "error": "no_sofa_match",
                    "home_tid": hk,
                    "away_tid": ak,
                    "score": f"{hs}-{aws}",
                    "round": rnd,
                }
            )
        else:
            issues.append(
                {
                    "tff_mac_id": mid,
                    "error": "ambiguous",
                    "candidates": [c["match_id"] for c in candidates],
                }
            )
    return out, issues


def running_scores(
    goals: list[dict], home_id: int, away_id: int, profiles_by_id: dict[int, dict]
) -> list[dict]:
    """
    goals: list with keys minute, goal_order, scorer_team_id (int), scorer_id
    Sort by (minute, goal_order), assign is_home and cumulative scores after each goal.
    """
    goals = sorted(goals, key=lambda g: (g["minute"], g.get("goal_order", 0)))
    h, a = 0, 0
    out: list[dict] = []
    for g in goals:
        st = g["scorer_team_id"]
        if st == home_id:
            h += 1
            is_home = True
        elif st == away_id:
            a += 1
            is_home = False
        else:
            # fallback: cannot place goal (e.g. missing team)
            is_home = st == home_id
            if is_home:
                h += 1
            else:
                a += 1
        out.append(
            {
                **g,
                "is_home": is_home,
                "home_score": h,
                "away_score": a,
            }
        )
    return out


def main() -> None:
    kulup_map = load_kulup_map(MAPPINGS)
    kisi_overrides = load_kisi_overrides(KISI_OVERRIDES)
    html = fetch_archive()
    mac_rounds = parse_mac_rounds(html)

    TFF_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    tff_m = list(csv.DictReader(open(TFF_ARTIFACT_DIR / "tff_match_index.csv", encoding="utf-8")))
    tff_g = list(csv.DictReader(open(TFF_ARTIFACT_DIR / "tff_goals_by_match.csv", encoding="utf-8")))
    gk = list(csv.DictReader(open(TFF_ARTIFACT_DIR / "tff_gol_kralligi.csv", encoding="utf-8")))
    sofa = list(csv.DictReader(open(SEASON_DIR / "matches.csv", encoding="utf-8")))
    profiles_by_id, profile_rows = load_profiles(SEASON_DIR / "player_profiles.csv")
    by_team_name, by_name, by_team_surname = build_player_index(profile_rows)

    kisi_primary_team: dict[int, int] = {}
    for row in gk:
        kisi_primary_team[int(row["tff_kisi_id"])] = kulup_map[int(row["tff_kulup_id"])]

    mac_to_match, link_issues = link_tff_mac_to_match(tff_m, sofa, kulup_map, mac_rounds)

    # Resolve every kisi_id used in goals
    kisi_ids = sorted({int(r["tff_kisi_id"]) for r in tff_g})
    kisi_resolution: dict[int, dict[str, Any]] = {}
    for kid in kisi_ids:
        # primary club from gol kralligi if present
        pteam = kisi_primary_team.get(kid)
        name_row = next((r for r in gk if int(r["tff_kisi_id"]) == kid), None)
        tff_name = name_row["player_name_tff"] if name_row else ""
        pid, how = resolve_player(
            tff_name,
            pteam,
            kid,
            kisi_overrides,
            by_team_name,
            by_name,
            by_team_surname,
            profiles_by_id,
        )
        kisi_resolution[kid] = {
            "tff_kisi_id": kid,
            "player_id": pid,
            "method": how,
            "tff_name": tff_name,
            "primary_team_id": pteam,
        }

    # Group goals by mac, attach match_id and scorer team (from profile at primary club
    # or any resolved id)
    by_mac: dict[int, list[dict]] = defaultdict(list)
    for row in tff_g:
        mid = int(row["tff_mac_id"])
        kid = int(row["tff_kisi_id"])
        res = kisi_resolution[kid]
        pid = res["player_id"]
        if pid is None:
            scorer_team = kisi_primary_team.get(kid)
        else:
            scorer_team = int(profiles_by_id[pid]["team_id"])
        by_mac[mid].append(
            {
                "tff_mac_id": mid,
                "minute": int(row["minute"]),
                "goal_order": int(row.get("goal_order") or 0),
                "tff_kisi_id": kid,
                "scorer_name_tff": row["scorer_name_tff"],
                "scorer_id": pid,
                "scorer_team_id": scorer_team,
            }
        )

    goal_rows_out: list[dict[str, Any]] = []
    super_final_rows: list[dict[str, Any]] = []
    unmapped_goals: list[dict] = []
    for mid, gls in by_mac.items():
        if mid in SUPER_FINAL_TFF_MAC_IDS:
            for g in gls:
                kid = g["tff_kisi_id"]
                pid = g.get("scorer_id")
                pname = (
                    profiles_by_id[pid]["name"]
                    if pid and pid in profiles_by_id
                    else g["scorer_name_tff"].title()
                )
                super_final_rows.append(
                    {
                        "tff_mac_id": mid,
                        "minute": g["minute"],
                        "scorer": pname,
                        "scorer_id": pid if pid is not None else "",
                        "tff_kisi_id": kid,
                        "note": "Spor Toto Super Final — not merged into league goals.csv",
                    }
                )
            continue
    for mid, gls in by_mac.items():
        if mid in SUPER_FINAL_TFF_MAC_IDS:
            continue
        mid_str = mac_to_match.get(mid)
        if not mid_str:
            for g in gls:
                unmapped_goals.append({**g, "reason": "tff_mac_unmapped"})
            continue
        sm = next((m for m in sofa if str(m["match_id"]) == mid_str), None)
        if not sm:
            continue
        hid, aid = int(sm["home_team_id"]), int(sm["away_team_id"])
        for g in gls:
            st = g["scorer_team_id"]
            pt = kisi_primary_team.get(g["tff_kisi_id"])
            if st is None or st not in (hid, aid):
                if pt is not None and pt in (hid, aid):
                    g["scorer_team_id"] = pt
                else:
                    g["scorer_team_id"] = hid
                    g["_side_fallback"] = True
        enriched = running_scores(gls, hid, aid, profiles_by_id)
        for g in enriched:
            pid = g["scorer_id"]
            pname = (
                profiles_by_id[pid]["name"]
                if pid and pid in profiles_by_id
                else g["scorer_name_tff"].title()
            )
            goal_rows_out.append(
                {
                    "match_id": mid_str,
                    "minute": g["minute"],
                    "added_time": "",
                    "scorer": pname,
                    "scorer_id": pid if pid is not None else "",
                    "assist": "",
                    "assist_id": "",
                    "goal_type": "regular",
                    "is_home": g["is_home"],
                    "home_score": g["home_score"],
                    "away_score": g["away_score"],
                    "_sort_order": g.get("goal_order", 0),
                }
            )

    goal_rows_out.sort(
        key=lambda r: (int(r["match_id"]), int(r["minute"]), int(r.get("_sort_order", 0)))
    )
    for r in goal_rows_out:
        r.pop("_sort_order", None)

    goals_path = SEASON_DIR / "goals.csv"
    fieldnames = [
        "match_id",
        "minute",
        "added_time",
        "scorer",
        "scorer_id",
        "assist",
        "assist_id",
        "goal_type",
        "is_home",
        "home_score",
        "away_score",
    ]
    with open(goals_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in goal_rows_out:
            w.writerow(row)

    sf_path = TFF_ARTIFACT_DIR / "goals_tff_super_final.csv"
    if super_final_rows:
        with open(sf_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "tff_mac_id",
                    "minute",
                    "scorer",
                    "scorer_id",
                    "tff_kisi_id",
                    "note",
                ],
            )
            w.writeheader()
            for row in sorted(
                super_final_rows, key=lambda r: (r["tff_mac_id"], r["minute"])
            ):
                w.writerow(row)

    mac_map_path = TFF_ARTIFACT_DIR / "tff_mac_to_match_id.csv"
    with open(mac_map_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["tff_mac_id", "match_id", "round_tff"])
        w.writeheader()
        for tr in tff_m:
            tid = int(tr["tff_mac_id"])
            w.writerow(
                {
                    "tff_mac_id": tid,
                    "match_id": mac_to_match.get(tid, ""),
                    "round_tff": mac_rounds.get(tid, ""),
                }
            )

    kisi_map_path = TFF_ARTIFACT_DIR / "tff_kisi_to_player_id.csv"
    with open(kisi_map_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "tff_kisi_id",
                "player_id",
                "resolution_method",
                "tff_name",
                "primary_team_id",
            ],
        )
        w.writeheader()
        for kid in kisi_ids:
            r = kisi_resolution[kid]
            w.writerow(
                {
                    "tff_kisi_id": kid,
                    "player_id": r["player_id"] if r["player_id"] is not None else "",
                    "resolution_method": r["method"],
                    "tff_name": r["tff_name"],
                    "primary_team_id": r.get("primary_team_id"),
                }
            )

    report = {
        "goals_written_league": len(goal_rows_out),
        "goals_tff_super_final": len(super_final_rows),
        "tff_goal_lines_total": len(tff_g),
        "mac_ids_total": len(tff_m),
        "mac_ids_mapped_league": len(mac_to_match),
        "link_issues": link_issues,
        "kisi_unresolved": [k for k, v in kisi_resolution.items() if v["player_id"] is None],
        "unmapped_league_goals": len(unmapped_goals),
        "notes": [
            "Assists and added_time are not on the TFF match pages scraped here.",
            "goal_type is always 'regular' in goals.csv (penalty/own-goal markers from TFF are not in tff_goals_by_match.csv).",
            "Four macIds are Spor Toto Super Final; they are excluded from league goals.csv and written to goals_tff_super_final.csv.",
            "Two fixtures in matches.csv are Postponed with no score; they cannot be filled until a result exists.",
            "TFF macId 99076 lists five scorers for a 4-0 score — one row may be spurious; cross-check if totals look wrong.",
            "is_home / running scores use scorer club from player_profiles (and TFF gol krallığı club); own goals can look wrong without pitch-level data.",
        ],
    }
    un_path = TFF_ARTIFACT_DIR / "tff_kisi_unresolved.csv"
    with open(un_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["tff_kisi_id", "tff_name", "primary_team_id", "hint"],
        )
        w.writeheader()
        for kid in report["kisi_unresolved"]:
            r = kisi_resolution[kid]
            w.writerow(
                {
                    "tff_kisi_id": kid,
                    "tff_name": r["tff_name"],
                    "primary_team_id": r.get("primary_team_id") or "",
                    "hint": "Add row to tff_mappings/tff_kisi_to_player_id_overrides.csv then re-run",
                }
            )

    with open(TFF_ARTIFACT_DIR / "tff_merge_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Wrote {goals_path} ({len(goal_rows_out)} league rows)")
    if super_final_rows:
        print(f"Wrote {sf_path} ({len(super_final_rows)} super-final rows)")
    print(f"Mapped league mac_ids: {len(mac_to_match)}/{len(tff_m) - len(SUPER_FINAL_TFF_MAC_IDS)} (super final excluded)")
    print(f"Unresolved kisi_id count: {len(report['kisi_unresolved'])}")
    unexpected = [
        x
        for x in link_issues
        if x.get("error") != "super_final_excluded_from_league_csv"
    ]
    if unexpected:
        print(f"Link issues (unexpected): {unexpected}", file=sys.stderr)


if __name__ == "__main__":
    main()
