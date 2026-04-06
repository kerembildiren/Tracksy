"""
CSV Dataset Exporter
sofascore-wrapper 1.1.1

Kullanım:
    python export.py                      # seçim menüsü gösterir
    python export.py --all                # tüm CSV'leri çıkar
    python export.py --season 2024        # belirli sezonu çıkar (yıl veya id)
    python export.py --module teams       # sadece takım verileri
    python export.py --module matches     # sadece maç verileri
    python export.py --module players     # sadece oyuncu verileri
    python export.py --module events      # sadece olaylar (gol/kart/değişiklik)
    python export.py --module stats       # sadece maç istatistikleri

Çıktı klasörü: ./data/<sezon_yili>/
    standings.csv         — puan durumu
    teams.csv             — takım profilleri
    matches.csv           — tüm maç sonuçları
    goals.csv             — goller
    cards.csv             — kartlar
    substitutions.csv     — değişiklikler
    match_stats.csv       — maç istatistikleri
    player_profiles.csv   — sezondaki kadro (maç kadroları /lineups birleştirilir; güncel /team/.../players değil)
    player_stats.csv      — oyuncu sezon istatistikleri (API’de varsa)
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import argparse
import csv
import os
import time

from sofascore_wrapper.api import SofascoreAPI
from sofascore_wrapper.league import League
from sofascore_wrapper.team import Team
from sofascore_wrapper.match import Match
from sofascore_wrapper.player import Player

LEAGUE_ID = 52 # Trendyol Süper Lig ID'si
RATE_DELAY = 0.35  # istek arası bekleme (saniye)


# ══════════════════════════════════════════════════════════════════════════════
# UTILS
# ══════════════════════════════════════════════════════════════════════════════
def write_csv(path: str, rows: list, fieldnames: list):
    if not rows:
        print(f"  ⚠  {path} — veri yok, atlandı")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓ {path}  ({len(rows)} satır)")


async def pick_season(api: SofascoreAPI, season_arg: str | None) -> dict:
    """
    season_arg None   → mevcut sezon
    season_arg '2024' → yıl ile ara (24/25 veya 2024)
    season_arg int str→ doğrudan id kullan
    """
    league = League(api, LEAGUE_ID)
    if season_arg is None:
        return await league.current_season()

    try:
        sid = int(season_arg)
        # 5+ haneli → doğrudan season id
        if sid > 9999:
            seasons = await league.get_seasons()
            for s in seasons:
                if s["id"] == sid:
                    return s
            raise ValueError(f"ID {sid} bulunamadı")
        # 4 haneli yıl → yıl eşleştir
        seasons = await league.get_seasons()
        for s in seasons:
            if str(sid) in s.get("year", ""):
                return s
        raise ValueError(f"{season_arg} yılı bulunamadı")
    except ValueError as e:
        raise SystemExit(f"Sezon hatası: {e}")


def data_dir(season: dict) -> str:
    year = season.get("year", str(season["id"])).replace("/", "-")
    return f"./data/{year}"


def load_match_rows_from_disk(out_dir: str) -> list:
    """Biten maç satırlarını matches.csv üzerinden okur (kadro çıkarımı için)."""
    path = os.path.join(out_dir, "matches.csv")
    if not os.path.isfile(path):
        return []
    rows_out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                row = {
                    "match_id": int(r["match_id"]),
                    "season_id": int(r["season_id"]) if r.get("season_id") else None,
                    "home_team_id": int(r["home_team_id"]) if r.get("home_team_id") else None,
                    "away_team_id": int(r["away_team_id"]) if r.get("away_team_id") else None,
                    "status_code": int(r["status_code"]) if r.get("status_code") is not None else None,
                }
            except (ValueError, KeyError, TypeError):
                continue
            rows_out.append(row)
    return rows_out


def load_played_match_ids_from_disk(out_dir: str) -> list:
    """matches.csv içinden status_code=100 (biten) maçların id listesi — olay yenileme için."""
    rows = load_match_rows_from_disk(out_dir)
    return [r["match_id"] for r in rows if r.get("status_code") == 100 and r.get("match_id")]


INCIDENT_RETRIES = 3

# SofaScore: bazı eski sezonlarda çoğu maçın /incidents yanıtında yalnızca HT/FT (period) var;
# gol/kart için incident satırları dönmez. Maç ID aralığı (ör. 192xxxx) ile sınırlı; playoff ile
# karıştırılmamalı — aynı sezon fikstüründe 258xxxx gibi az sayıda “tam” kayıt olabilir.
SEASON_LEGACY_INCIDENT_GAP: frozenset[int] = frozenset({3831})  # Süper Lig 11/12
# Bu sezonlarda /event/{id}/statistics çoğunlukla 404 — gereksiz istek ve log gürültüsü.
SEASON_SKIP_MATCH_STATS: frozenset[int] = frozenset({3831})


def _legacy_incident_note(season_id: int | None, played_matches: int, goal_rows: int) -> str:
    if season_id not in SEASON_LEGACY_INCIDENT_GAP:
        return ""
    return (
        f"\n  ⚠ Sezon {season_id} (11/12): SofaScore API çoğu maçta gol/kart/detay döndürmüyor "
        f"(yalnızca ~{goal_rows} gol satırı / {played_matches} biten maç). "
        "Bu, playoff fikstüründen çok eski maç kayıtlarının API’de sınırlı olmasından kaynaklanır. "
        "Oyuncu bazlı gol/assist için harici kaynak (ör. resmi istatistik, Mackolik arşivi) gerekebilir.\n"
    )


def _iter_lineup_players(side_block: dict):
    if not side_block:
        return
    for entry in side_block.get("players") or []:
        p = entry.get("player")
        if p and p.get("id"):
            yield p
    for mp in side_block.get("missingPlayers") or []:
        if isinstance(mp, dict):
            p = mp.get("player")
            if p and p.get("id"):
                yield p


def _profile_from_lineup_player(p: dict, team_id: int) -> dict:
    return {
        "player_id": p.get("id"),
        "name": p.get("name"),
        "short_name": p.get("shortName"),
        "position": p.get("position"),
        "jersey_number": p.get("jerseyNumber"),
        "height": p.get("height"),
        "preferred_foot": p.get("preferredFoot"),
        "date_of_birth_ts": p.get("dateOfBirthTimestamp"),
        "team_id": team_id,
        "market_value_eur": (p.get("proposedMarketValueRaw") or {}).get("value"),
        "nationality": (p.get("country") or {}).get("name"),
        "roster_source": "season_lineups",
    }


def _merge_profile(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if v is None or v == "":
            continue
        if out.get(k) is None or out.get(k) == "":
            out[k] = v
    return out


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1: SCOREBOARD
# ══════════════════════════════════════════════════════════════════════════════
async def export_standings(api: SofascoreAPI, season: dict, out_dir: str):
    print("→ Puan durumu...")
    data = await League(api, LEAGUE_ID).standings(season["id"])
    rows = []
    for group in data.get("standings", []):
        for row in group.get("rows", []):
            rows.append({
                "position":      row.get("position"),
                "team":          row.get("team", {}).get("name"),
                "team_id":       row.get("team", {}).get("id"),
                "matches":       row.get("matches"),
                "wins":          row.get("wins"),
                "draws":         row.get("draws"),
                "losses":        row.get("losses"),
                "goals_for":     row.get("scoresFor"),
                "goals_against": row.get("scoresAgainst"),
                "goal_diff":     row.get("scoreDiffFormatted"),
                "points":        row.get("points"),
            })
    write_csv(f"{out_dir}/standings.csv", rows, list(rows[0].keys()) if rows else [])
    return rows  # takım listesi için kullanılacak


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2: TEAMS
# ══════════════════════════════════════════════════════════════════════════════
async def export_teams(api: SofascoreAPI, season: dict, out_dir: str, team_ids: list):
    print(f"→ Takım profilleri ({len(team_ids)} takım)...")
    profiles, stats_rows = [], []

    for tid in team_ids:
        try:
            t = Team(api, tid)
            info_data, stats_data = await asyncio.gather(
                t.get_team(), t.league_stats(LEAGUE_ID, season["id"]),
                return_exceptions=True,
            )

            # Profil
            if not isinstance(info_data, Exception):
                team = info_data.get("team", {})
                venue = team.get("venue", {})
                manager = team.get("manager", {})
                form = info_data.get("pregameForm", {})
                profiles.append({
                    "team_id":           team.get("id"),
                    "name":              team.get("name"),
                    "short_name":        team.get("shortName"),
                    "name_code":         team.get("nameCode"),
                    "manager":           manager.get("name"),
                    "stadium":           venue.get("name"),
                    "city":              venue.get("city", {}).get("name"),
                    "capacity":          venue.get("capacity"),
                    "primary_color":     team.get("teamColors", {}).get("primary"),
                    "form":              ",".join(form.get("form", [])) if form else None,
                    "avg_rating":        form.get("avgRating") if form else None,
                })

            # İstatistik
            if not isinstance(stats_data, Exception):
                s = stats_data.get("statistics", {})
                stats_rows.append({"team_id": tid, "season_id": season["id"], **{
                    k: s.get(k) for k in [
                        "matches", "goalsScored", "goalsConceded", "assists",
                        "shots", "shotsOnTarget", "bigChances", "bigChancesCreated",
                        "averageBallPossession", "totalPasses", "accuratePassesPercentage",
                        "tackles", "interceptions", "clearances", "saves",
                        "yellowCards", "redCards", "avgRating",
                    ]
                }})

            time.sleep(RATE_DELAY)
        except Exception as ex:
            print(f"    ⚠ Takım {tid}: {ex}")

    write_csv(f"{out_dir}/teams.csv", profiles, [
        "team_id", "name", "short_name", "name_code",
        "manager", "stadium", "city", "capacity",
        "primary_color", "form", "avg_rating",
    ])
    write_csv(f"{out_dir}/team_stats.csv", stats_rows, [
        "team_id", "season_id", "matches",
        "goalsScored", "goalsConceded", "assists",
        "shots", "shotsOnTarget", "bigChances", "bigChancesCreated",
        "averageBallPossession", "totalPasses", "accuratePassesPercentage",
        "tackles", "interceptions", "clearances", "saves",
        "yellowCards", "redCards", "avgRating",
    ])


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3: MATCHES
# ══════════════════════════════════════════════════════════════════════════════
async def export_matches(api: SofascoreAPI, season: dict, out_dir: str) -> tuple:
    """Tüm haftaların maçlarını çeker. (oynanan id listesi, tüm maç satırları) döner."""
    print("→ Maçlar (tüm haftalar)...")
    league = League(api, LEAGUE_ID)
    rounds_data = await league.rounds(season["id"])
    all_rounds = rounds_data.get("rounds", [])
    rows, played_ids = [], []

    for r in all_rounds:
        rn = r.get("round")
        try:
            result = await league.league_fixtures_per_round(season["id"], rn)
            events = result if isinstance(result, list) else result.get("events", [])
            for e in events:
                status = e.get("status", {})
                home_score = e.get("homeScore", {}).get("current")
                rows.append({
                    "match_id":        e.get("id"),
                    "season_id":       season["id"],
                    "round":           rn,
                    "start_timestamp": e.get("startTimestamp"),
                    "home_team":       e.get("homeTeam", {}).get("name"),
                    "home_team_id":    e.get("homeTeam", {}).get("id"),
                    "away_team":       e.get("awayTeam", {}).get("name"),
                    "away_team_id":    e.get("awayTeam", {}).get("id"),
                    "home_score":      home_score,
                    "away_score":      e.get("awayScore", {}).get("current"),
                    "home_ht":         e.get("homeScore", {}).get("period1"),
                    "away_ht":         e.get("awayScore", {}).get("period1"),
                    "winner_code":     e.get("winnerCode"),  # 1=ev 2=dep 3=beraberlik
                    "status":          status.get("description"),
                    "status_code":     status.get("code"),
                })
                if status.get("code") == 100:  # Ended
                    played_ids.append(e["id"])
            time.sleep(RATE_DELAY)
        except Exception as ex:
            print(f"    ⚠ Hafta {rn}: {ex}")

    write_csv(f"{out_dir}/matches.csv", rows, [
        "match_id", "season_id", "round", "start_timestamp",
        "home_team", "home_team_id", "away_team", "away_team_id",
        "home_score", "away_score", "home_ht", "away_ht",
        "winner_code", "status", "status_code",
    ])
    if season["id"] in SEASON_LEGACY_INCIDENT_GAP:
        print(
            "  ℹ 11/12: Özel sezon formatı (ek maçlar) nedeniyle hafta başına maç sayısı değişebilir; "
            "gol/kart detayı SofaScore’da çoğu maç için API’de kısıtlıdır."
        )
    return played_ids, rows


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4: EVENTS
# ══════════════════════════════════════════════════════════════════════════════
async def export_events(
    api: SofascoreAPI,
    match_ids: list,
    out_dir: str,
    season_id: int | None = None,
):
    print(f"→ Olaylar ({len(match_ids)} maç)...")
    goals, cards, subs = [], [], []

    for mid in match_ids:
        data = None
        last_ex = None
        for attempt in range(INCIDENT_RETRIES):
            try:
                data = await Match(api, mid).incidents()
                break
            except Exception as ex:
                last_ex = ex
                time.sleep(RATE_DELAY * (attempt + 2))
        if data is None:
            print(f"    ⚠ Maç {mid} olayları: {last_ex}")
            continue
        try:
            for inc in data.get("incidents", []):
                inc_type = inc.get("incidentType", "")
                p = inc.get("player") or {}
                is_home = inc.get("isHome")
                minute  = inc.get("time")

                if inc_type == "goal":
                    assist = inc.get("assist1") or {}
                    goals.append({
                        "match_id":   mid,
                        "minute":     minute,
                        "added_time": inc.get("addedTime"),
                        "scorer":     p.get("name"),
                        "scorer_id":  p.get("id"),
                        "assist":     assist.get("name"),
                        "assist_id":  assist.get("id"),
                        "goal_type":  inc.get("incidentClass", "regular"),
                        "is_home":    is_home,
                        "home_score": inc.get("homeScore"),
                        "away_score": inc.get("awayScore"),
                    })

                elif inc_type == "card":
                    cards.append({
                        "match_id":  mid,
                        "minute":    minute,
                        "added_time": inc.get("addedTime"),
                        "player":    p.get("name"),
                        "player_id": p.get("id"),
                        "card_type": inc.get("incidentClass", "yellow"),
                        "is_home":   is_home,
                    })

                elif inc_type == "substitution":
                    p_in  = inc.get("playerIn")  or {}
                    p_out = inc.get("playerOut") or {}
                    subs.append({
                        "match_id":      mid,
                        "minute":        minute,
                        "player_in":     p_in.get("name"),
                        "player_in_id":  p_in.get("id"),
                        "player_out":    p_out.get("name"),
                        "player_out_id": p_out.get("id"),
                        "is_home":       is_home,
                    })
            time.sleep(RATE_DELAY)
        except Exception as ex:
            print(f"    ⚠ Maç {mid} olay parse: {ex}")

    write_csv(f"{out_dir}/goals.csv", goals, [
        "match_id", "minute", "added_time",
        "scorer", "scorer_id", "assist", "assist_id",
        "goal_type", "is_home", "home_score", "away_score",
    ])
    write_csv(f"{out_dir}/cards.csv", cards, [
        "match_id", "minute", "added_time",
        "player", "player_id", "card_type", "is_home",
    ])
    write_csv(f"{out_dir}/substitutions.csv", subs, [
        "match_id", "minute",
        "player_in", "player_in_id", "player_out", "player_out_id", "is_home",
    ])
    print(_legacy_incident_note(season_id, len(match_ids), len(goals)), end="")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 5: MATCH STATISTICS
# ══════════════════════════════════════════════════════════════════════════════
async def export_match_stats(
    api: SofascoreAPI,
    match_ids: list,
    out_dir: str,
    season_id: int | None = None,
    force: bool = False,
):
    if season_id in SEASON_SKIP_MATCH_STATS and not force:
        print(
            "→ Maç istatistikleri: bu sezon (11/12) için SofaScore çoğu maçta /statistics 404 döndürür; "
            "atlandı. Zorunlu denemek için export_match_stats(..., force=True)."
        )
        return
    print(f"→ Maç istatistikleri ({len(match_ids)} maç)...")
    rows = []
    err_404 = 0
    err_other = 0

    for mid in match_ids:
        data = None
        last_ex = None
        for attempt in range(INCIDENT_RETRIES):
            try:
                data = await Match(api, mid).stats()
                break
            except Exception as ex:
                last_ex = ex
                time.sleep(RATE_DELAY * (attempt + 2))
        if data is None:
            if last_ex and "404" in str(last_ex):
                err_404 += 1
            else:
                err_other += 1
                print(f"    ⚠ Maç {mid} istatistik: {last_ex}")
            continue
        try:
            for period in data.get("statistics", []):
                if period.get("period") != "ALL":
                    continue
                flat = {"match_id": mid}
                for group in period.get("groups", []):
                    for item in group.get("statisticsItems", []):
                        key = item.get("key", "").replace(" ", "_").lower()
                        flat[f"home_{key}"] = item.get("homeValue")
                        flat[f"away_{key}"] = item.get("awayValue")
                rows.append(flat)
            time.sleep(RATE_DELAY)
        except Exception as ex:
            print(f"    ⚠ Maç {mid} istatistik parse: {ex}")

    if rows:
        all_keys = list(dict.fromkeys(k for r in rows for k in r.keys()))
        write_csv(f"{out_dir}/match_stats.csv", rows, all_keys)
    if err_404 or err_other:
        print(
            f"  ℹ Maç istatistik özeti: 404={err_404}, diğer={err_other} "
            "(eski sezonlarda 404 normal sayılabilir)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 6: PLAYERS
# ══════════════════════════════════════════════════════════════════════════════
async def export_players(
    api: SofascoreAPI,
    season: dict,
    out_dir: str,
    team_ids: list,
    match_rows: list | None = None,
    fetch_league_stats: bool = True,
):
    """
    Sezon kadrosu: /team/{id}/players güncel kadrodur; bu yüzden o sezonun biten
    maçlarında /event/{match_id}/lineups yanıtı birleştirilir.
    """
    if match_rows is None:
        match_rows = load_match_rows_from_disk(out_dir)
    ended = [
        r for r in match_rows
        if r.get("status_code") == 100
        and r.get("match_id")
        and r.get("home_team_id") is not None
        and r.get("away_team_id") is not None
    ]
    if not ended:
        print("  ⚠ Oyuncular: matches.csv yok veya biten maç yok — atlandı")
        return

    print(f"→ Oyuncular (sezon kadrosu, {len(ended)} maç kadrosundan)...")
    # team_id -> player_id -> profil
    by_team: dict = {}
    lineup_errors = 0

    for row in ended:
        mid = row["match_id"]
        hid, aid = row["home_team_id"], row["away_team_id"]
        try:
            data = await api._get(f"/event/{mid}/lineups")
        except Exception:
            lineup_errors += 1
            time.sleep(RATE_DELAY)
            continue

        for side_key, tid in (("home", hid), ("away", aid)):
            side = data.get(side_key) or {}
            for p in _iter_lineup_players(side):
                pid = p["id"]
                prof = _profile_from_lineup_player(p, tid)
                by_team.setdefault(tid, {})
                if pid not in by_team[tid]:
                    by_team[tid][pid] = prof
                else:
                    by_team[tid][pid] = _merge_profile(by_team[tid][pid], prof)
        time.sleep(RATE_DELAY)

    if lineup_errors:
        print(f"    ⚠ Kadro: {lineup_errors} maçta /lineups alınamadı")

    profiles = []
    for tid in team_ids:
        pmap = by_team.get(tid) or {}
        if not pmap:
            print(f"    ⚠ Takım {tid}: bu sezonda lineup’tan oyuncu yok")
            continue
        print(f"    ✓ Takım {tid}: {len(pmap)} oyuncu (lineups)")
        for prow in pmap.values():
            profiles.append(prow)

    write_csv(f"{out_dir}/player_profiles.csv", profiles, [
        "player_id", "name", "short_name", "position", "jersey_number",
        "height", "preferred_foot", "date_of_birth_ts",
        "team_id", "market_value_eur", "nationality", "roster_source",
    ])

    if not fetch_league_stats:
        return

    print(f"→ Oyuncu sezon istatistikleri ({len(profiles)} oyuncu, API müsaitse)...")
    stats_rows = []
    for prow in profiles:
        pid, tid = prow["player_id"], prow["team_id"]
        try:
            stats_data = await Player(api, pid).league_stats(LEAGUE_ID, season["id"])
            s = stats_data.get("statistics", {})
            if s:
                stats_rows.append({
                    "player_id":              pid,
                    "team_id":                tid,
                    "season_id":              season["id"],
                    "appearances":            s.get("appearances"),
                    "matches_started":        s.get("matchesStarted"),
                    "minutes_played":         s.get("minutesPlayed"),
                    "goals":                  s.get("goals"),
                    "assists":                s.get("assists"),
                    "expected_goals":         s.get("expectedGoals"),
                    "expected_assists":       s.get("expectedAssists"),
                    "yellow_cards":           s.get("yellowCards"),
                    "red_cards":              s.get("redCards"),
                    "rating":                 s.get("rating"),
                    "total_shots":            s.get("totalShots"),
                    "shots_on_target":        s.get("shotsOnTarget"),
                    "accurate_passes":        s.get("accuratePasses"),
                    "total_passes":           s.get("totalPasses"),
                    "accurate_passes_pct":    s.get("accuratePassesPercentage"),
                    "key_passes":             s.get("keyPasses"),
                    "tackles":                s.get("tackles"),
                    "interceptions":          s.get("interceptions"),
                    "successful_dribbles":    s.get("successfulDribbles"),
                    "ground_duels_won_pct":   s.get("groundDuelsWonPercentage"),
                    "aerial_duels_won_pct":   s.get("aerialDuelsWonPercentage"),
                    "saves":                  s.get("saves"),
                    "clean_sheets":           s.get("cleanSheet"),
                    "goals_conceded":         s.get("goalsConceded"),
                    "big_chances_created":    s.get("bigChancesCreated"),
                    "big_chances_missed":     s.get("bigChancesMissed"),
                })
        except Exception:
            pass
        time.sleep(RATE_DELAY)
    write_csv(f"{out_dir}/player_stats.csv", stats_rows, [
        "player_id", "team_id", "season_id",
        "appearances", "matches_started", "minutes_played",
        "goals", "assists", "expected_goals", "expected_assists",
        "yellow_cards", "red_cards", "rating",
        "total_shots", "shots_on_target",
        "accurate_passes", "total_passes", "accurate_passes_pct", "key_passes",
        "tackles", "interceptions", "successful_dribbles",
        "ground_duels_won_pct", "aerial_duels_won_pct",
        "saves", "clean_sheets", "goals_conceded",
        "big_chances_created", "big_chances_missed",
    ])


# ══════════════════════════════════════════════════════════════════════════════
# MAIN THINGS
# ══════════════════════════════════════════════════════════════════════════════
MODULES = ["teams", "matches", "events", "stats", "players"]


async def run(module: str | None, season_arg: str | None, run_all: bool):
    api = SofascoreAPI()
    try:
        season = await pick_season(api, season_arg)
        sid = season["id"]
        out_dir = data_dir(season)
        os.makedirs(out_dir, exist_ok=True)

        print(f"\nSezon: {season.get('name')}  (id={sid})")
        print(f"Çıktı: {out_dir}\n")

        # Her zaman önce puan durumunu çekerek takım listesi al
        standings_rows = await export_standings(api, season, out_dir)
        team_ids = [r["team_id"] for r in standings_rows if r.get("team_id")]

        modules_to_run = MODULES if run_all else ([module] if module else [])

        if not modules_to_run:
            # Interactive menu
            print("\nHangi modülleri çalıştırmak istiyorsunuz?")
            for i, m in enumerate(MODULES, 1):
                print(f"  {i}. {m}")
            print("  0. Hepsi")
            choice = input("Seçim (virgülle ayırın, örn: 1,3): ").strip()
            if choice == "0":
                modules_to_run = MODULES
            else:
                indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip().isdigit()]
                modules_to_run = [MODULES[i] for i in indices if 0 <= i < len(MODULES)]

        played_ids = []
        match_rows_for_players = None

        if "matches" in modules_to_run or "events" in modules_to_run or "stats" in modules_to_run:
            played_ids, match_rows_for_players = await export_matches(api, season, out_dir)

        if "teams" in modules_to_run:
            await export_teams(api, season, out_dir, team_ids)

        if "events" in modules_to_run and played_ids:
            await export_events(api, played_ids, out_dir, season_id=sid)

        if "stats" in modules_to_run and played_ids:
            await export_match_stats(api, played_ids, out_dir, season_id=sid)

        if "players" in modules_to_run:
            await export_players(
                api, season, out_dir, team_ids, match_rows=match_rows_for_players
            )

        print(f"\n✅ Tamamlandı! → {out_dir}")

    finally:
        await api.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trendyol Süper Lig Kaggle Dataset Exporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--module",
        choices=MODULES,
        help="Çalıştırılacak modül",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Tüm modülleri çalıştır",
    )
    parser.add_argument(
        "--season",
        help="Sezon yılı (örn: 2024) veya sezon ID (örn: 61627). Boş = mevcut sezon.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.module, args.season, args.all))