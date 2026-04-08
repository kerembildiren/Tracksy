"""
Generate a random 3×3 grid where every cell has enough valid players from the index.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from labels import country_label_turkish
from player_index import (
    BIG_FOUR,
    BIG_THREE,
    PlayerRecord,
    nationalities_with_min_players,
    all_team_ids,
)


class AxisKind(str, Enum):
    TEAM = "team"
    COUNTRY = "country"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# Her hücre için ayrı ayrı uygulanır (9 kutu, hepsi need >= olmalı)
MIN_POOL_EASY = 10
MIN_POOL_MEDIUM = 10
MIN_POOL_HARD = 5

# Ülke + takım kesişimlerinde dar havuzları azaltmak için
HYBRID_NAT_MIN_PLAYERS = 22


@dataclass
class Criterion:
    kind: AxisKind
    value: object
    label: str


@dataclass
class GeneratedCell:
    row: int
    col: int
    valid_ids: Set[int]
    canonical_id: int
    hint_position: Optional[str]
    hint_seasons: int


@dataclass
class GeneratedGrid:
    mode: str
    difficulty: str
    rows: List[Criterion]
    cols: List[Criterion]
    cells: List[List[GeneratedCell]]


def _pool_team_team(players: Dict[int, PlayerRecord], a: int, b: int) -> Set[int]:
    if a == b:
        return {p for p, r in players.items() if a in r.teams}
    return {p for p, r in players.items() if a in r.teams and b in r.teams}


def _pool_team_country(players: Dict[int, PlayerRecord], team_id: int, nat: str) -> Set[int]:
    out: Set[int] = set()
    for pid, r in players.items():
        if team_id not in r.teams:
            continue
        if nat in r.nationalities:
            out.add(pid)
            continue
        if r.primary_nationality() == nat:
            out.add(pid)
    return out


def _pool_country_country(players: Dict[int, PlayerRecord], na: str, nb: str) -> Set[int]:
    na, nb = str(na), str(nb)
    if na == nb:
        out: Set[int] = set()
        for pid, r in players.items():
            if na in r.nationalities or r.primary_nationality() == na:
                out.add(pid)
        return out
    out = set()
    for pid, r in players.items():
        if na in r.nationalities and nb in r.nationalities:
            out.add(pid)
    return out


def _cell_pool(
    players: Dict[int, PlayerRecord],
    row: Criterion,
    col: Criterion,
) -> Set[int]:
    pairs = [(row, col), (col, row)]
    for a, b in pairs:
        if a.kind == AxisKind.TEAM and b.kind == AxisKind.TEAM:
            return _pool_team_team(players, int(a.value), int(b.value))
        if a.kind == AxisKind.TEAM and b.kind == AxisKind.COUNTRY:
            return _pool_team_country(players, int(a.value), str(b.value))
        if a.kind == AxisKind.COUNTRY and b.kind == AxisKind.TEAM:
            return _pool_team_country(players, int(b.value), str(a.value))
        if a.kind == AxisKind.COUNTRY and b.kind == AxisKind.COUNTRY:
            return _pool_country_country(players, str(a.value), str(b.value))
    return set()


def _min_required(difficulty: Difficulty) -> int:
    if difficulty == Difficulty.EASY:
        return MIN_POOL_EASY
    if difficulty == Difficulty.MEDIUM:
        return MIN_POOL_MEDIUM
    return MIN_POOL_HARD


def _pick_canonical(players: Dict[int, PlayerRecord], pool: Set[int]) -> int:
    best = -1
    best_key = (-1, "")
    for pid in pool:
        r = players[pid]
        sc = r.season_count
        name = r.name or r.short_name or str(pid)
        key = (sc, name)
        if key > best_key:
            best_key = key
            best = pid
    return best


def _hint_fields(players: Dict[int, PlayerRecord], pid: int) -> Tuple[Optional[str], int]:
    r = players[pid]
    pos = r.primary_position()
    return pos, r.season_count


def _crit_team(tid: int, team_names: Dict[int, str]) -> Criterion:
    label = team_names.get(tid) or f"Kulüp #{tid}"
    return Criterion(AxisKind.TEAM, tid, label)


def _crit_country(nat_key: str) -> Criterion:
    return Criterion(AxisKind.COUNTRY, nat_key, country_label_turkish(nat_key))


def _team_pool_for_difficulty(
    team_ids_list: List[int], non_big: List[int], diff: Difficulty
) -> List[int]:
    if diff == Difficulty.HARD:
        return list(non_big)
    return list(team_ids_list)


def _sample_mixed_teams(
    tpool: List[int],
    n_need: int,
    diff: Difficulty,
    rng: random.Random,
) -> Optional[List[int]]:
    if n_need < 1 or len(tpool) < n_need:
        return None
    four = list(BIG_FOUR)
    if diff == Difficulty.EASY:
        rest = [t for t in tpool if t not in BIG_FOUR]
        if n_need >= 4:
            extra = n_need - 4
            if len(rest) < extra:
                return None
            picked = four + (rng.sample(rest, k=extra) if extra else [])
            rng.shuffle(picked)
            return picked
        if len(four) < n_need:
            return None
        return rng.sample(four, k=n_need)
    if diff == Difficulty.MEDIUM:
        rest = [t for t in tpool if t not in BIG_FOUR]
        if n_need < 2:
            return rng.sample(tpool, k=n_need)
        need_rest = n_need - 2
        if len(rest) < need_rest:
            return None
        picked = rng.sample(four, k=2) + (rng.sample(rest, k=need_rest) if need_rest else [])
        rng.shuffle(picked)
        return picked
    return rng.sample(tpool, k=n_need)


def _try_mixed(
    players: Dict[int, PlayerRecord],
    team_names: Dict[int, str],
    team_ids_list: List[int],
    non_big: List[int],
    nats: List[str],
    rng: random.Random,
    diff: Difficulty,
) -> Optional[GeneratedGrid]:
    tpool = _team_pool_for_difficulty(team_ids_list, non_big, diff)
    for _ in range(120):
        row_kinds = [rng.choice([AxisKind.TEAM, AxisKind.COUNTRY]) for _ in range(3)]
        col_kinds = [rng.choice([AxisKind.TEAM, AxisKind.COUNTRY]) for _ in range(3)]
        if all(k == AxisKind.COUNTRY for k in row_kinds) and all(
            k == AxisKind.COUNTRY for k in col_kinds
        ):
            continue
        n_rt = sum(1 for k in row_kinds if k == AxisKind.TEAM)
        n_ct = sum(1 for k in col_kinds if k == AxisKind.TEAM)
        n_rc = 3 - n_rt
        n_cc = 3 - n_ct
        if diff == Difficulty.EASY and n_rt + n_ct < 3:
            continue
        if len(nats) < n_rc + n_cc:
            continue
        if n_rt + n_ct > 0:
            teams_picked = _sample_mixed_teams(tpool, n_rt + n_ct, diff, rng)
            if teams_picked is None:
                continue
        else:
            teams_picked = []
        countries_picked = rng.sample(nats, k=n_rc + n_cc)
        it_t = iter(teams_picked)
        it_c = iter(countries_picked)
        rows: List[Criterion] = []
        for k in row_kinds:
            if k == AxisKind.TEAM:
                rows.append(_crit_team(next(it_t), team_names))
            else:
                rows.append(_crit_country(next(it_c)))
        cols = []
        for k in col_kinds:
            if k == AxisKind.TEAM:
                cols.append(_crit_team(next(it_t), team_names))
            else:
                cols.append(_crit_country(next(it_c)))
        grid = _finalize(players, "mixed", rows, cols, diff)
        if grid:
            return grid
    return None


def try_generate(
    players: Dict[int, PlayerRecord],
    team_names: Dict[int, str],
    *,
    difficulty: str = "medium",
    max_attempts: int = 8000,
    rng: Optional[random.Random] = None,
) -> Optional[GeneratedGrid]:
    rng = rng or random.Random()
    try:
        diff = Difficulty(difficulty)
    except ValueError:
        diff = Difficulty.MEDIUM

    team_ids_list = sorted(all_team_ids(players))
    non_big = [t for t in team_ids_list if t not in BIG_THREE]
    nats_lo = nationalities_with_min_players(players, minimum=8)
    nats_hi = nationalities_with_min_players(players, minimum=HYBRID_NAT_MIN_PLAYERS)

    if len(nats_lo) < 3 or len(non_big) < 3:
        return None
    if diff != Difficulty.HARD and len(non_big) < 6:
        pass
    if diff == Difficulty.HARD and len(non_big) < 6:
        return None

    for _ in range(max_attempts):
        mode = rng.choices(
            ["six_teams", "hybrid", "mixed"],
            weights=[32, 32, 36],
            k=1,
        )[0]
        if mode == "six_teams":
            grid = _try_six_teams(players, team_names, team_ids_list, non_big, rng, diff)
        elif mode == "hybrid":
            if len(nats_hi) < 3:
                nats_use = nats_lo
            else:
                nats_use = nats_hi
            grid = _try_hybrid(players, team_names, non_big, nats_use, rng, diff)
        else:
            if len(nats_hi) < 3:
                nats_use = nats_lo
            else:
                nats_use = nats_hi
            grid = _try_mixed(
                players, team_names, team_ids_list, non_big, nats_use, rng, diff
            )
        if grid:
            return grid
    return None


def _pick_teams_six(
    team_ids_list: List[int],
    non_big: List[int],
    rng: random.Random,
    diff: Difficulty,
) -> Optional[List[int]]:
    non_four = [t for t in team_ids_list if t not in BIG_FOUR]
    four = list(BIG_FOUR)
    if diff == Difficulty.EASY:
        if len(non_four) < 2:
            return None
        extra = rng.sample(non_four, k=2)
        six = four + extra
        rng.shuffle(six)
        return six

    if diff == Difficulty.MEDIUM:
        if len(non_four) < 4:
            return None
        from_four = rng.sample(four, k=2)
        from_rest = rng.sample(non_four, k=4)
        six = from_four + from_rest
        rng.shuffle(six)
        return six

    # HARD — değişmedi: büyük üçlü dışı altı takım
    if len(non_big) < 6:
        return None
    six = rng.sample(non_big, k=6)
    rng.shuffle(six)
    return six


def _try_six_teams(
    players: Dict[int, PlayerRecord],
    team_names: Dict[int, str],
    team_ids_list: List[int],
    non_big: List[int],
    rng: random.Random,
    diff: Difficulty,
) -> Optional[GeneratedGrid]:
    six = _pick_teams_six(team_ids_list, non_big, rng, diff)
    if not six:
        return None
    rows = [_crit_team(six[0], team_names), _crit_team(six[1], team_names), _crit_team(six[2], team_names)]
    cols = [_crit_team(six[3], team_names), _crit_team(six[4], team_names), _crit_team(six[5], team_names)]
    return _finalize(players, "six_teams", rows, cols, diff)


def _pick_teams_three(non_big: List[int], rng: random.Random, diff: Difficulty) -> Optional[List[int]]:
    four = list(BIG_FOUR)
    if diff == Difficulty.EASY:
        return rng.sample(four, k=3)

    if diff == Difficulty.MEDIUM:
        rest_pool = [t for t in non_big if t not in BIG_FOUR]
        if len(rest_pool) < 1:
            return None
        from_four = rng.sample(four, k=2)
        from_rest = rng.sample(rest_pool, k=1)
        t = from_four + from_rest
        rng.shuffle(t)
        return t

    if len(non_big) < 3:
        return None
    t = rng.sample(non_big, k=3)
    rng.shuffle(t)
    return t


def _try_hybrid(
    players: Dict[int, PlayerRecord],
    team_names: Dict[int, str],
    non_big: List[int],
    nats: List[str],
    rng: random.Random,
    diff: Difficulty,
) -> Optional[GeneratedGrid]:
    three_teams = _pick_teams_three(non_big, rng, diff)
    if not three_teams:
        return None
    countries = rng.sample(nats, k=3)

    team_crits = [_crit_team(three_teams[0], team_names), _crit_team(three_teams[1], team_names), _crit_team(three_teams[2], team_names)]
    country_crits = [_crit_country(countries[0]), _crit_country(countries[1]), _crit_country(countries[2])]
    if rng.random() < 0.5:
        rows, cols = team_crits, country_crits
    else:
        rows, cols = country_crits, team_crits
    return _finalize(players, "hybrid", rows, cols, diff)


def _finalize(
    players: Dict[int, PlayerRecord],
    mode: str,
    rows: List[Criterion],
    cols: List[Criterion],
    difficulty: Difficulty,
) -> Optional[GeneratedGrid]:
    cells: List[List[GeneratedCell]] = []
    need = _min_required(difficulty)
    # 3×3: her (satır, sütun) kesişimi için aynı eşik; biri bile yetmezse tüm grid reddedilir
    for i in range(3):
        row_cells: List[GeneratedCell] = []
        for j in range(3):
            pool = _cell_pool(players, rows[i], cols[j])
            if len(pool) < need:
                return None
            cid = _pick_canonical(players, pool)
            pos, sc = _hint_fields(players, cid)
            row_cells.append(
                GeneratedCell(
                    row=i,
                    col=j,
                    valid_ids=set(pool),
                    canonical_id=cid,
                    hint_position=pos,
                    hint_seasons=sc,
                )
            )
        cells.append(row_cells)
    return GeneratedGrid(
        mode=mode,
        difficulty=difficulty.value,
        rows=rows,
        cols=cols,
        cells=cells,
    )
