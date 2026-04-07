"""
Full player list (all seasons in superlig_data) + eligibility for the daily answer.

Daily target must satisfy at least one of:
  - 30+ career goals+assists (player_stats + goals.csv where stats yok)
  - 5+ distinct seasons in the league
  - At least one season with a club that won the league that season

Search pool: every player who appears in the aggregated index (player_profiles across seasons).
"""

from __future__ import annotations

import csv
import os
import pickle
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
GRID_ROOT = os.path.join(ROOT, "..", "grid_game")
if GRID_ROOT not in sys.path:
    sys.path.insert(0, GRID_ROOT)

from player_index import load_or_build_index  # noqa: E402

DEFAULT_DATA = os.path.join(ROOT, "..", "superlig_data")
CACHE_NAME = ".player_guess_catalog_v4.pkl"

# Daily answer must pass at least one
MIN_GA_FOR_ELIGIBLE = 30
MIN_SEASONS_FOR_ELIGIBLE = 5


def _birth_year_from_ts(ts_raw: str) -> Optional[int]:
    if not ts_raw or not str(ts_raw).strip():
        return None
    try:
        ts = int(float(ts_raw))
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).year
    except (OSError, OverflowError, ValueError):
        return None


def _load_champions_by_season(data_root: str) -> Dict[str, int]:
    """season folder key -> winning team_id (standings position == 1)."""
    out: Dict[str, int] = {}
    for season in sorted(os.listdir(data_root)):
        folder = os.path.join(data_root, season)
        if not os.path.isdir(folder):
            continue
        path = os.path.join(folder, "standings.csv")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            pos = str(row.get("position", "")).strip()
            if pos != "1":
                continue
            try:
                out[season] = int(row["team_id"])
            except (KeyError, ValueError, TypeError):
                continue
            break
    return out


def _safe_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    s = str(val).strip()
    if not s or s in ("-", "—", "N/A", "n/a", "null", "None"):
        return default
    try:
        return int(float(s.replace(",", ".")))
    except (ValueError, TypeError):
        return default


def _aggregate_from_goals_csv(
    folder: str,
    goals: Dict[int, int],
    assists: Dict[int, int],
) -> None:
    """
    player_stats.csv olmayan sezonlarda (ör. 01-02 … 10-11, 12-13) kariyer gol/asist
    goals.csv üzerinden toplanır. 11-12 ile aynı kolon adları (scorer_id, assist_id).
    """
    path = os.path.join(folder, "goals.csv")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return
        for row in reader:
            pid = _safe_int(row.get("scorer_id"), -1)
            if pid > 0:
                goals[pid] = goals.get(pid, 0) + 1
            apid = _safe_int(row.get("assist_id"), -1)
            if apid > 0:
                assists[apid] = assists.get(apid, 0) + 1


def _aggregate(data_root: str) -> Tuple[
    Dict[int, int],
    Dict[int, int],
    Dict[int, Dict[int, int]],
    Dict[int, int],
    Dict[int, Dict[int, int]],
    Set[Tuple[int, str, int]],
]:
    """
    goals, assists, apps_by_team[pid][tid],
    birth_years,
    profile_apps[pid][tid] (row counts in player_profiles),
    season_team_pairs (player_id, season_key, team_id) from player_stats.
    """
    goals: Dict[int, int] = {}
    assists: Dict[int, int] = {}
    apps_by_team: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    birth_years: Dict[int, int] = {}
    profile_apps: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    season_team_pairs: Set[Tuple[int, str, int]] = set()

    for season in sorted(os.listdir(data_root)):
        folder = os.path.join(data_root, season)
        if not os.path.isdir(folder):
            continue

        pstats = os.path.join(folder, "player_stats.csv")
        if os.path.isfile(pstats):
            with open(pstats, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    try:
                        pid = int(row["player_id"])
                        tid = int(row["team_id"])
                    except (KeyError, ValueError, TypeError):
                        continue
                    g = _safe_int(row.get("goals"))
                    a = _safe_int(row.get("assists"))
                    ap = _safe_int(row.get("appearances"))
                    goals[pid] = goals.get(pid, 0) + g
                    assists[pid] = assists.get(pid, 0) + a
                    apps_by_team[pid][tid] += ap
                    season_team_pairs.add((pid, season, tid))
        else:
            _aggregate_from_goals_csv(folder, goals, assists)

        prof = os.path.join(folder, "player_profiles.csv")
        if os.path.isfile(prof):
            with open(prof, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    try:
                        pid = int(row["player_id"])
                        tid_raw = row.get("team_id")
                        if not tid_raw:
                            continue
                        tid = int(tid_raw)
                    except (KeyError, ValueError, TypeError):
                        continue
                    profile_apps[pid][tid] += 1
                    if pid not in birth_years:
                        y = _birth_year_from_ts(row.get("date_of_birth_ts") or "")
                        if y is not None:
                            birth_years[pid] = y

    return goals, assists, dict(apps_by_team), birth_years, dict(profile_apps), season_team_pairs


def _won_championship(
    pid: int,
    season_team_pairs: Set[Tuple[int, str, int]],
    champions: Dict[str, int],
) -> bool:
    for p, season, tid in season_team_pairs:
        if p != pid:
            continue
        ch = champions.get(season)
        if ch is not None and ch == tid:
            return True
    return False


def _top_club(
    pid: int,
    apps_by_team: Dict[int, Dict[int, int]],
    profile_apps: Dict[int, Dict[int, int]],
    team_names: Dict[int, str],
) -> Tuple[int, str, int]:
    """Returns (team_id, name, apps) using stats appearances, else profile row counts."""
    st = apps_by_team.get(pid) or {}
    pr = profile_apps.get(pid) or {}
    if st:
        tid, apps = max(st.items(), key=lambda x: (x[1], -x[0]))
    elif pr:
        tid, apps = max(pr.items(), key=lambda x: (x[1], -x[0]))
    else:
        return 0, "?", 0
    name = team_names.get(tid) or f"Kulüp #{tid}"
    return tid, name, apps


def _eligible(
    goals_assists: int,
    seasons_played: int,
    won_championship: bool,
) -> bool:
    return (
        goals_assists >= MIN_GA_FOR_ELIGIBLE
        or seasons_played >= MIN_SEASONS_FOR_ELIGIBLE
        or won_championship
    )


def build_catalog(data_root: str) -> Tuple[List[Dict[str, Any]], List[int], Dict[int, str]]:
    data_root = os.path.abspath(data_root)
    players, team_names = load_or_build_index(data_root, use_cache=True)
    champions = _load_champions_by_season(data_root)
    goals, assists, apps_by_team, birth_years, profile_apps, season_team_pairs = _aggregate(
        data_root
    )

    pool: List[Dict[str, Any]] = []
    for pid, rec in players.items():
        nat = rec.primary_nationality()
        pos = rec.primary_position()
        gtot = goals.get(pid, 0)
        atot = assists.get(pid, 0)
        ga = gtot + atot
        top_tid, top_name, top_apps = _top_club(pid, apps_by_team, profile_apps, team_names)
        won = _won_championship(pid, season_team_pairs, champions)
        by = birth_years.get(pid)
        daily_ok = _eligible(ga, rec.season_count, won)

        pool.append(
            {
                "player_id": pid,
                "name": rec.name or rec.short_name or f"#{pid}",
                "short_name": rec.short_name or rec.name or f"#{pid}",
                "position": pos or "?",
                "birth_year": by,
                "nationality": nat or "",
                "seasons_played": rec.season_count,
                "goals_total": gtot,
                "assists_total": atot,
                "goals_assists": ga,
                "top_club_id": top_tid,
                "top_club_name": top_name,
                "top_club_apps": top_apps,
                "won_championship": won,
                "_daily_ok": daily_ok,
            }
        )

    pool.sort(key=lambda x: x["player_id"])
    eligible_ids = sorted(p["player_id"] for p in pool if p.get("_daily_ok"))
    for p in pool:
        p.pop("_daily_ok", None)
        p.pop("won_championship", None)
    return pool, eligible_ids, team_names


def cache_path() -> str:
    return os.path.join(ROOT, CACHE_NAME)


def load_catalog(
    data_root: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[int], Dict[int, str]]:
    root = os.path.abspath(data_root or DEFAULT_DATA)
    cp = cache_path()
    if os.path.isfile(cp):
        with open(cp, "rb") as f:
            data = pickle.load(f)
        if isinstance(data, tuple) and len(data) == 3:
            return data[0], data[1], data[2]
        # older 2-tuple cache → rebuild
    out = build_catalog(root)
    os.makedirs(os.path.dirname(cp) or ".", exist_ok=True)
    with open(cp, "wb") as f:
        pickle.dump(out, f)
    return out


def player_by_id(pool: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {p["player_id"]: p for p in pool}


# Backwards name
def load_pool(data_root: Optional[str] = None):
    return load_catalog(data_root)
