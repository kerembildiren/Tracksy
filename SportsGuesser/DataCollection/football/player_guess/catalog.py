"""
Full player list (all seasons in superlig_data) + eligibility for the daily answer.

Daily target must satisfy all of:
  (A) At least one of: 30+ career G+A, 5+ Süper Lig sezonu, veya o sezon şampiyonu
      olduğu bir kulüpte yer almak
  (B) En az 2 ayrı sezon FB/GS/BJK/TS kadrosunda olmak VEYA toplam 10+ Süper Lig sezonu

Search pool: every player in the aggregated index (player_profiles); günlük çekiliş
sadece daily_ok oyuncular arasından.
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

from player_index import PlayerRecord, load_or_build_index  # noqa: E402

DEFAULT_DATA = os.path.join(ROOT, "..", "superlig_data")
CACHE_NAME = ".player_guess_catalog_v8.pkl"

# Daily answer must pass at least one (geniş havuz)
MIN_GA_FOR_ELIGIBLE = 30
MIN_SEASONS_FOR_ELIGIBLE = 5

# Günlük hedef ek daraltma: bilinirlik (ikisi birden gerekmez, biri yeter)
# - Büyük dörtlüde (BJK, Trabzonspor, Fenerbahçe, Galatasaray) en az 2 ayrı sezon, veya
# - Süper Lig'de toplam en az 10 sezon
BIG_FOUR_TEAM_IDS: frozenset = frozenset({3050, 3051, 3052, 3061})  # BJK, TS, FB, GS
MIN_BIG4_DISTINCT_SEASONS = 2
MIN_TOTAL_SEASONS_RECOGNIZABLE = 10


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
    goals.csv varsa o sezonda gol/asist buradan toplanır (tüm scorer/assist kayıtları).
    Kolonlar: scorer_id, assist_id.
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
    goals, assists: her sezonda goals.csv varsa olaydan; yoksa player_stats.
    apps_by_team, season_team_pairs: player_stats satırlarından (varsa).
    birth_years, profile_apps: player_profiles.
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

        goals_path = os.path.join(folder, "goals.csv")
        has_goals_csv = os.path.isfile(goals_path)

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
                    # player_stats çoğu sezonda eksik; goals.csv tam olay listesi.
                    # Çift sayımı önlemek için goals.csv varken G/A'yı stats'tan ekleme.
                    if not has_goals_csv:
                        goals[pid] = goals.get(pid, 0) + g
                        assists[pid] = assists.get(pid, 0) + a
                    apps_by_team[pid][tid] += ap
                    season_team_pairs.add((pid, season, tid))

        if has_goals_csv:
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


def _season_sort_key(season_key: str) -> int:
    part = season_key.split("-")[0] if season_key else ""
    return int(part) if part.isdigit() else 0


def _season_display_calendar_span(season_key: str) -> str:
    """Veri anahtarı 09-10 -> gösterim 2009-2010 (sezon başlangıç yılı - bitiş yılı)."""
    part = season_key.split("-")[0] if season_key else ""
    if not part.isdigit():
        return season_key
    y = int(part)
    year_start = 2000 + y if y < 70 else 1900 + y
    return f"{year_start}-{year_start + 1}"


def _group_consecutive_season_keys(keys: List[str]) -> List[List[str]]:
    if not keys:
        return []
    sk = sorted(keys, key=_season_sort_key)
    groups: List[List[str]] = []
    cur = [sk[0]]
    for i in range(1, len(sk)):
        if _season_sort_key(sk[i]) == _season_sort_key(sk[i - 1]) + 1:
            cur.append(sk[i])
        else:
            groups.append(cur)
            cur = [sk[i]]
    groups.append(cur)
    return groups


def format_top_club_seasons_hint_sentence(sorted_season_keys: List[str]) -> str:
    """
    En çok oynanan kulüp için sezonları anlatır (kulüp adı yok).
    Üst üste oynanan bloklar: ilk ve son takvim yılı + sezon sayısı.
    Kopuk tek sezonlar: virgül ve 'aynı kulüpte' vurgusuyla birleştirilir.
    """
    if not sorted_season_keys:
        return ""
    groups = _group_consecutive_season_keys(list(sorted_season_keys))
    run_parts: List[str] = []
    single_labels: List[str] = []
    for g in groups:
        if len(g) == 1:
            single_labels.append(_season_display_calendar_span(g[0]))
        else:
            n = len(g)
            a = _season_display_calendar_span(g[0])
            b = _season_display_calendar_span(g[-1])
            run_parts.append(f"{a} ile {b} arasında üst üste {n} sezon")

    single_phrase = ""
    if len(single_labels) == 1:
        single_phrase = f"{single_labels[0]} sezonunda"
    elif len(single_labels) >= 2:
        single_phrase = (
            ", ".join(single_labels[:-1]) + " ve " + single_labels[-1] + " sezonlarında"
        )

    if not run_parts and not single_phrase:
        return ""

    if not run_parts:
        body = single_phrase
    elif not single_phrase:
        body = "; ".join(run_parts) if len(run_parts) > 1 else run_parts[0]
    else:
        head = "; ".join(run_parts)
        body = f"{head}; ayrıca aynı kulüpte {single_phrase}"

    return (
        "En çok Süper Lig sezonu geçirdiği kulüpte (isim gizli) "
        f"{body} kadroda bulundu."
    )


def _championship_seasons_count(rec: PlayerRecord, champions: Dict[str, int]) -> int:
    """Oyuncunun kadrosunda olduğu ve takımın şampiyon olduğu sezon sayısı (lig şampiyonluğu)."""
    n = 0
    for tid, seas in rec.team_seasons.items():
        for s in seas:
            if champions.get(s) == tid:
                n += 1
    return n


def _career_timeline_rows(rec: PlayerRecord, team_names: Dict[int, str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for tid, seas in rec.team_seasons.items():
        tname = team_names.get(tid) or f"Kulüp #{tid}"
        for s in seas:
            rows.append({"season": s, "team": tname})
    rows.sort(key=lambda r: (_season_sort_key(r["season"]), r["team"]))
    return rows


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


def _career_team_ids(
    pid: int,
    rec: PlayerRecord,
    apps_by_team: Dict[int, Dict[int, int]],
    profile_apps: Dict[int, Dict[int, int]],
) -> Set[int]:
    """Süper Lig'de oynadığı tüm takımlar (ipuçlarında sarı için doğru oyuncu tarafında kullanılır)."""
    out: Set[int] = set(rec.teams)
    out.update((apps_by_team.get(pid) or {}).keys())
    out.update((profile_apps.get(pid) or {}).keys())
    return out


def _top_club(
    pid: int,
    rec: PlayerRecord,
    apps_by_team: Dict[int, Dict[int, int]],
    profile_apps: Dict[int, Dict[int, int]],
    team_names: Dict[int, str],
) -> Tuple[int, str, int]:
    """
    En çok Süper Lig sezonu geçirilen kulüp; eşitlikte istatistik maç sayısı, yoksa profil satır sayısı.
    (Sadece appearances ile max almak, az maçlı güncel takımı yanlışlıkla öne çıkarabiliyordu.)
    """
    ts = rec.team_seasons
    st = apps_by_team.get(pid) or {}
    pr = profile_apps.get(pid) or {}
    candidates: Set[int] = set(ts.keys()) | set(st.keys()) | set(pr.keys())
    if not candidates:
        return 0, "?", 0

    def sort_key(tid: int) -> Tuple[int, int, int, int]:
        seasons = len(ts.get(tid, frozenset()))
        a_st = int(st.get(tid, 0) or 0)
        a_pr = int(pr.get(tid, 0) or 0)
        apps = a_st if a_st > 0 else a_pr
        return (seasons, apps, a_st, a_pr)

    best = max(candidates, key=sort_key)
    a_st = int(st.get(best, 0) or 0)
    a_pr = int(pr.get(best, 0) or 0)
    top_apps = a_st if a_st > 0 else a_pr
    name = team_names.get(best) or f"Kulüp #{best}"
    return best, name, top_apps


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


def _recognizable_for_daily(rec: PlayerRecord) -> bool:
    """Günlük cevap: en az 2 sezon dörtlüde veya kariyerde en az 10 Süper Lig sezonu."""
    big4_seasons: Set[str] = set()
    for tid in BIG_FOUR_TEAM_IDS:
        big4_seasons |= rec.team_seasons.get(tid, set())
    if len(big4_seasons) >= MIN_BIG4_DISTINCT_SEASONS:
        return True
    if rec.season_count >= MIN_TOTAL_SEASONS_RECOGNIZABLE:
        return True
    return False


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
        top_tid, top_name, top_apps = _top_club(
            pid, rec, apps_by_team, profile_apps, team_names
        )
        career_ids = _career_team_ids(pid, rec, apps_by_team, profile_apps)
        won = _won_championship(pid, season_team_pairs, champions)
        by = birth_years.get(pid)
        daily_ok = _eligible(ga, rec.season_count, won) and _recognizable_for_daily(rec)
        ch_count = _championship_seasons_count(rec, champions)
        top_club_seasons_sorted = sorted(
            rec.team_seasons.get(top_tid, set()), key=_season_sort_key
        ) if top_tid else []
        career_timeline = _career_timeline_rows(rec, team_names)

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
                "career_team_ids": sorted(career_ids),
                "championship_count": ch_count,
                "top_club_seasons_sorted": top_club_seasons_sorted,
                "career_timeline": career_timeline,
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
