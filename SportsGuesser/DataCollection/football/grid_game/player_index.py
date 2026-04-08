"""
Build a player lookup from superlig_data/**/player_profiles.csv
"""

from __future__ import annotations

import csv
import os
import pickle
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

BIG_THREE: Set[int] = {3050, 3052, 3061}
# Beşiktaş, Trabzonspor, Fenerbahçe, Galatasaray — kolay/orta grid seçimlerinde kullanılır.
BIG_FOUR: Set[int] = {3050, 3051, 3052, 3061}


@dataclass
class PlayerRecord:
    player_id: int
    name: str
    short_name: str
    teams: Set[int] = field(default_factory=set)
    nationalities: Set[str] = field(default_factory=set)
    positions: Set[str] = field(default_factory=set)
    seasons: Set[str] = field(default_factory=set)
    # team_id -> season folder names (e.g. "23-24") for Süper Lig roster rows
    team_seasons: Dict[int, Set[str]] = field(default_factory=dict)

    @property
    def season_count(self) -> int:
        return len(self.seasons)

    def primary_nationality(self) -> Optional[str]:
        if not self.nationalities:
            return None
        if len(self.nationalities) == 1:
            return next(iter(self.nationalities))
        # Prefer longest string (often full country name); tie-break sort
        return sorted(self.nationalities, key=lambda s: (-len(s), s))[0]

    def primary_position(self) -> Optional[str]:
        if not self.positions:
            return None
        order = {"G": 0, "D": 1, "M": 2, "F": 3}
        for p in sorted(self.positions, key=lambda x: order.get(x, 9)):
            return p
        return next(iter(self.positions))


def _norm_nat(s: str) -> str:
    return (s or "").strip()


def load_team_names(data_root: str) -> Dict[int, str]:
    """team_id -> display name from tüm standings.csv dosyaları."""
    names: Dict[int, str] = {}
    for season in sorted(os.listdir(data_root)):
        path = os.path.join(data_root, season, "standings.csv")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                tid = row.get("team_id")
                team = row.get("team")
                if not tid or not team:
                    continue
                try:
                    names[int(tid)] = team.strip()
                except ValueError:
                    continue
    for tid, label in [(3050, "Beşiktaş"), (3052, "Fenerbahçe"), (3061, "Galatasaray")]:
        names.setdefault(tid, label)
    return names


def fill_team_names_from_matches(
    data_root: str, names: Dict[int, str], needed: Set[int]
) -> None:
    """Eksik takım adlarını matches.csv satırlarından doldurur."""
    missing = needed - set(names.keys())
    if not missing:
        return
    for season in sorted(os.listdir(data_root)):
        path = os.path.join(data_root, season, "matches.csv")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                for tid_field, nm_field in (
                    ("home_team_id", "home_team"),
                    ("away_team_id", "away_team"),
                ):
                    try:
                        tid = int(row[tid_field])
                    except (KeyError, ValueError, TypeError):
                        continue
                    if tid in missing and row.get(nm_field):
                        names[tid] = row[nm_field].strip()
                        missing.discard(tid)
        if not missing:
            break


def build_player_index(data_root: str) -> Tuple[Dict[int, PlayerRecord], Dict[int, str]]:
    players: Dict[int, PlayerRecord] = {}
    team_names = load_team_names(data_root)

    for season in sorted(os.listdir(data_root)):
        if not os.path.isdir(os.path.join(data_root, season)):
            continue
        path = os.path.join(data_root, season, "player_profiles.csv")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "player_id" not in reader.fieldnames:
                continue
            for row in reader:
                try:
                    pid = int(row["player_id"])
                except (KeyError, ValueError):
                    continue
                tid_raw = row.get("team_id")
                if not tid_raw:
                    continue
                try:
                    tid = int(tid_raw)
                except ValueError:
                    continue

                rec = players.get(pid)
                if rec is None:
                    rec = PlayerRecord(
                        player_id=pid,
                        name=(row.get("name") or "").strip(),
                        short_name=(row.get("short_name") or "").strip(),
                    )
                    players[pid] = rec

                rec.teams.add(tid)
                rec.seasons.add(season)
                if tid not in rec.team_seasons:
                    rec.team_seasons[tid] = set()
                rec.team_seasons[tid].add(season)
                nat = _norm_nat(row.get("nationality", ""))
                if nat:
                    rec.nationalities.add(nat)
                pos = (row.get("position") or "").strip()
                if pos:
                    rec.positions.add(pos)
                if not rec.name and row.get("name"):
                    rec.name = row["name"].strip()
                if not rec.short_name and row.get("short_name"):
                    rec.short_name = row["short_name"].strip()

    needed_ids = all_team_ids(players)
    fill_team_names_from_matches(data_root, team_names, needed_ids)
    for tid in needed_ids:
        if tid not in team_names:
            team_names[tid] = f"Kulüp #{tid}"

    return players, team_names


def cache_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, ".player_index_cache_v4.pkl")


def load_or_build_index(data_root: str, use_cache: bool = True):
    """Returns (players dict, team_names dict)."""
    base = os.path.abspath(data_root)
    cp = cache_path()
    if use_cache and os.path.isfile(cp):
        with open(cp, "rb") as f:
            return pickle.load(f)
    players, team_names = build_player_index(base)
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp, "wb") as f:
        pickle.dump((players, team_names), f)
    return players, team_names


def nationalities_with_min_players(
    players: Dict[int, PlayerRecord], minimum: int = 8
) -> List[str]:
    counts: Dict[str, int] = {}
    for p in players.values():
        n = p.primary_nationality()
        if n:
            counts[n] = counts.get(n, 0) + 1
    return [n for n, c in counts.items() if c >= minimum]


def all_team_ids(players: Dict[int, PlayerRecord]) -> Set[int]:
    s: Set[int] = set()
    for p in players.values():
        s |= p.teams
    return s
