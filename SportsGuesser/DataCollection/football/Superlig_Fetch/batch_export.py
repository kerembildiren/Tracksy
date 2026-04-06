"""
Batch Dataset Exporter — 2001-2026 Süper Lig (SofaScore API)
sofascore-wrapper 1.1.1

Veri akışı (tutarlı yapı):
    standings → matches (tüm haftalar) → events (gol/kart/değişiklik, maç başına /incidents)
    → match_stats → [opsiyonel] teams + player_profiles + player_stats

Kullanım:
    python batch_export.py --data-dir ../superlig_data
    python batch_export.py --all-modules --data-dir ../superlig_data
    python batch_export.py --no-resume --season 2011 --data-dir ../superlig_data
    python batch_export.py --audit --data-dir ../superlig_data
    python batch_export.py --refetch-events --start 2011 --end 2012 --data-dir ../superlig_data

--refetch-events:
    Mevcut matches.csv'deki biten maç ID'leriyle goals/cards/substitutions + match_stats
    yeniden çekilir (gol satırı eksik sezonlar için; tam batch'e gerek yok).

Çıktı: <data-dir>/<YY-YY>/
    standings.csv, matches.csv, goals.csv, cards.csv, substitutions.csv, match_stats.csv
    (--all-modules: teams.csv, team_stats.csv, player_profiles.csv, player_stats.csv)

Not: player_stats.csv SofaScore'da eski sezonlarda kısmen veya hiç olmayabilir; gol/kart için
    asıl kaynak events modülüdür.

Sezon tamamlandı: .done (--no-resume ile yeniden tam indirme).
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
import csv
import os
import time

from sofascore_wrapper.api import SofascoreAPI
from sofascore_wrapper.league import League

LEAGUE_ID = 52
RATE_DELAY = 0.35

# 2001-2026 aralığı (01/02 → 2001, 25/26 → 2025)
START_YEAR = 2001
END_YEAR = 2026  # 25/26 sezonu (API'de varsa)


# ══════════════════════════════════════════════════════════════════════════════
# SEASON HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def parse_start_year(year_str: str) -> int | None:
    """
    '01/02' → 2001
    '24/25' → 2024
    '99/00' → 1999
    """
    try:
        short = int(year_str.split("/")[0])
        # 2-digit year: 00-29 → 2000s, 30-99 → 1900s
        return 2000 + short if short <= 29 else 1900 + short
    except Exception:
        return None


def season_out_dir(season: dict, data_base: str) -> str:
    year = season.get("year", str(season["id"])).replace("/", "-")
    return os.path.join(data_base, year)


def is_done(out_dir: str) -> bool:
    return os.path.isfile(os.path.join(out_dir, ".done"))


def _count_csv_rows(path: str) -> int:
    if not os.path.isfile(path):
        return -1
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return max(0, sum(1 for _ in f) - 1)
    except OSError:
        return -1


def audit_seasons_on_disk(data_base: str) -> None:
    """
    Biten maç başına düşen gol satırı Süper Lig'de tipik ~2.3–2.9 aralığındadır.
    Çok düşükse (ör. 11-12'de ~71 gol / 330 maç) olaylar yeniden çekilmeli.
    """
    print(f"\n{'folder':<10} {'ended':>6} {'goals':>7} {'g/m':>6} {'cards':>7} {'subs':>7}  note")
    print("-" * 72)
    for name in sorted(os.listdir(data_base)):
        folder = os.path.join(data_base, name)
        if not os.path.isdir(folder) or "-" not in name:
            continue
        mpath = os.path.join(folder, "matches.csv")
        gpath = os.path.join(folder, "goals.csv")
        cpath = os.path.join(folder, "cards.csv")
        spath = os.path.join(folder, "substitutions.csv")
        ended = 0
        if os.path.isfile(mpath):
            with open(mpath, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("status_code") == "100":
                        ended += 1
        gn = _count_csv_rows(gpath)
        cn = _count_csv_rows(cpath)
        sn = _count_csv_rows(spath)
        gpm = (gn / ended) if ended > 0 and gn >= 0 else 0.0
        note = ""
        if ended == 0:
            note = "no matches"
        elif gn < 0:
            note = "no goals.csv"
        elif gpm < 1.2:
            note = "LIKELY_INCOMPLETE_EVENTS"
        elif gpm < 1.8:
            note = "check_events"
        avg = f"{gpm:.2f}" if ended else "-"
        print(f"{name:<10} {ended:>6} {gn:>7} {avg:>6} {cn:>7} {sn:>7}  {note}")


def has_squad_export(out_dir: str) -> bool:
    """Lineup tabanlı kadro export'u tamam mı? (Eski /team/.../players CSV'leri roster_source içermez.)"""
    path = os.path.join(out_dir, "player_profiles.csv")
    if not os.path.isfile(path) or os.path.getsize(path) < 50:
        return False
    try:
        with open(path, encoding="utf-8") as f:
            header = f.readline()
            if "roster_source" not in header:
                return False
            return sum(1 for _ in f) >= 1
    except OSError:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT EXPORT MODULES FROM export.py
# ══════════════════════════════════════════════════════════════════════════════
from export import (
    export_standings,
    export_teams,
    export_matches,
    export_events,
    export_match_stats,
    export_players,
    load_match_rows_from_disk,
    load_played_match_ids_from_disk,
)


# ══════════════════════════════════════════════════════════════════════════════
# BATCH RUNNER
# ══════════════════════════════════════════════════════════════════════════════

async def run_squad_only(
    api: SofascoreAPI,
    season: dict,
    out_dir: str,
    name: str,
    team_ids: list,
    fetch_player_stats: bool = True,
):
    await export_teams(api, season, out_dir, team_ids)
    if not load_match_rows_from_disk(out_dir):
        print("  ⚠ matches.csv yok veya boş — kadro için önce maçları indirin (tam batch veya export matches).")
        return
    await export_players(
        api,
        season,
        out_dir,
        team_ids,
        fetch_league_stats=fetch_player_stats,
    )
    print(f"  [OK] Kadro / oyuncu CSV -> {out_dir}")


async def run_season(
    api: SofascoreAPI,
    season: dict,
    all_modules: bool,
    resume: bool,
    squad_only: bool,
    data_base: str,
    skip_player_stats: bool = False,
):
    out_dir = season_out_dir(season, data_base)
    sid = season["id"]
    name = season.get("name", season.get("year", str(sid)))

    if squad_only:
        if resume and has_squad_export(out_dir):
            print(f"  >> Atlandı (kadro zaten var): {name}")
            return
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"  Sezon (sadece kadro): {name}  (id={sid})")
        print(f"  Cikti: {out_dir}")
        print(f"{'='*60}")
        try:
            standings_rows = await export_standings(api, season, out_dir)
            team_ids = [r["team_id"] for r in standings_rows if r.get("team_id")]
            await run_squad_only(
                api, season, out_dir, name, team_ids,
                fetch_player_stats=not skip_player_stats,
            )
        except Exception as ex:
            print(f"  [HATA] {name}: {ex}")
        return

    if resume and is_done(out_dir):
        if all_modules and not has_squad_export(out_dir):
            os.makedirs(out_dir, exist_ok=True)
            print(f"\n{'='*60}")
            print(f"  Sezon (kadro eki, .done mevcut): {name}  (id={sid})")
            print(f"  Cikti: {out_dir}")
            print(f"{'='*60}")
            try:
                standings_rows = await export_standings(api, season, out_dir)
                team_ids = [r["team_id"] for r in standings_rows if r.get("team_id")]
                await run_squad_only(
                    api, season, out_dir, name, team_ids,
                    fetch_player_stats=not skip_player_stats,
                )
            except Exception as ex:
                print(f"  [HATA] {name}: {ex}")
        else:
            print(f"  >> Atlandı (zaten tamamlandı): {name}")
        return

    os.makedirs(out_dir, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"  Sezon: {name}  (id={sid})")
    print(f"  Cikti: {out_dir}")
    print(f"{'='*60}")

    try:
        standings_rows = await export_standings(api, season, out_dir)
        team_ids = [r["team_id"] for r in standings_rows if r.get("team_id")]

        played_ids, match_rows = await export_matches(api, season, out_dir)

        await export_events(api, played_ids, out_dir, season_id=sid)
        await export_match_stats(api, played_ids, out_dir, season_id=sid)

        if all_modules:
            await export_teams(api, season, out_dir, team_ids)
            await export_players(
                api,
                season,
                out_dir,
                team_ids,
                match_rows=match_rows,
                fetch_league_stats=not skip_player_stats,
            )

        # Tüm modüller başarıyla tamamlandı — .done işaret dosyası yaz
        with open(os.path.join(out_dir, ".done"), "w") as f:
            f.write("ok")
        print(f"  [OK] {name} tamamlandi -> {out_dir}")

    except Exception as ex:
        print(f"  [HATA] {name}: {ex}")


async def run_refetch_events(
    api: SofascoreAPI,
    season: dict,
    data_base: str,
):
    """matches.csv kalır; goals/cards/substitutions + match_stats API'den yenilenir."""
    out_dir = season_out_dir(season, data_base)
    name = season.get("name", season.get("year", str(season["id"])))
    mfile = os.path.join(out_dir, "matches.csv")
    if not os.path.isfile(mfile):
        print(f"  [ATLA] {name}: matches.csv yok → önce tam batch veya --no-resume ile maçları indirin.")
        return
    played_ids = load_played_match_ids_from_disk(out_dir)
    if not played_ids:
        print(f"  [ATLA] {name}: biten maç yok (status_code=100).")
        return
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n  --refetch-events: {name}  → {len(played_ids)} maç")
    sid = season["id"]
    await export_events(api, played_ids, out_dir, season_id=sid)
    await export_match_stats(api, played_ids, out_dir, season_id=sid)
    print(f"  [OK] Olaylar güncellendi → {out_dir}")


async def run(args):
    data_base = os.path.abspath(args.data_dir)

    if getattr(args, "audit", False):
        audit_seasons_on_disk(data_base)
        return

    api = SofascoreAPI()
    try:
        league = League(api, LEAGUE_ID)
        all_seasons = await league.get_seasons()

        # Yıl aralığına göre filtrele
        start = args.start or START_YEAR
        end   = args.end   or END_YEAR

        if args.season:
            # Tek sezon modu
            target_year = int(args.season)
            seasons = [s for s in all_seasons if parse_start_year(s.get("year", "")) == target_year]
            if not seasons:
                raise SystemExit(f"[HATA] {args.season} yili icin sezon bulunamadi.")
        else:
            seasons = [
                s for s in all_seasons
                if start <= (parse_start_year(s.get("year", "")) or 0) <= end
            ]
            # Eski -> Yeni sirala
            seasons.sort(key=lambda s: parse_start_year(s.get("year", "")) or 0)

        if getattr(args, "refetch_events", False):
            print(f"\n--refetch-events: {len(seasons)} sezon (matches.csv → goals/cards/subs + match_stats)")
            print(f"Çıktı: {data_base}\n")
            for i, season in enumerate(seasons, 1):
                year_str = season.get("year", "?")
                print(f"[{i}/{len(seasons)}] {year_str}")
                await run_refetch_events(api, season, data_base)
                time.sleep(0.5)
            print(f"\n[TAMAMLANDI] Olay yenileme bitti. Veriler: {data_base}")
            return

        print(f"\nToplam {len(seasons)} sezon islenecek ({start}/{str(start+1)[-2:]} - {end}/{str(end+1)[-2:]})")
        print(f"Cikti kok klasoru: {data_base}")
        if args.squad_only:
            print("Mod: Sadece kadro (standings + teams + player_profiles/stats)")
        elif args.all_modules:
            print("Mod: Tum moduller (takim + oyuncu dahil) - Bu cok zaman alacak!")
        resume_txt = "Acik (tamamlananlar atlanir)" if not args.no_resume else "Kapali (hepsi yeniden indirilir)"
        print(f"Resume: {resume_txt}\n")

        for i, season in enumerate(seasons, 1):
            year_str = season.get("year", "?")
            print(f"[{i}/{len(seasons)}] {year_str}", end="  ")
            await run_season(
                api,
                season,
                args.all_modules,
                resume=not args.no_resume,
                squad_only=args.squad_only,
                data_base=data_base,
                skip_player_stats=args.skip_player_stats,
            )
            time.sleep(1.0)  # sezonlar arası ek bekleme

        print(f"\n[TAMAMLANDI] Batch export bitti! Toplam {len(seasons)} sezon.")
        print(f"   Veriler: {data_base}")

    finally:
        await api.close()


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trendyol Super Lig - 2001-2026 Batch Dataset Exporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="CSV cikis kok klasoru (ornek: ../superlig_data)",
    )
    parser.add_argument(
        "--squad-only",
        action="store_true",
        help="Sadece standings + takim profili + kadro/oyuncu istatistigi (maç/olay indirmez)",
    )
    parser.add_argument(
        "--skip-player-stats",
        action="store_true",
        help="Kadroyu (player_profiles) yazar ama oyuncu basina league_stats istegi yapmaz (cok daha hizli)",
    )
    parser.add_argument(
        "--all-modules",
        action="store_true",
        help="Tam batch ile takim ve oyuncu modullerini de calistir (cok yavas, her sezon ~1 saat)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Tamamlanan sezonları da yeniden indir",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help=f"Başlangıç yılı (varsayılan: {START_YEAR})",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help=f"Bitiş yılı (varsayılan: {END_YEAR})",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="Tek sezon başlangıç yılı (örn: 2015 → 2015/16 sezonu)",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Ağ yok: data-dir altındaki sezonları tarar; maç/gol oranı düşükse uyarır.",
    )
    parser.add_argument(
        "--refetch-events",
        action="store_true",
        help="matches.csv'den biten maç ID'leriyle goals/cards/substitutions + match_stats yenile (API gerekir).",
    )
    args = parser.parse_args()
    asyncio.run(run(args))
