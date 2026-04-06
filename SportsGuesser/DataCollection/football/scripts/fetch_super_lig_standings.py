"""
Fetch Turkish Super Lig standings from FBRef (2001-2002 through 2024-2025).
For each season: team name, rank, MP, W, D, L, GF, GA, GD, Pts, and notes (champion/relegation).
Builds a deduplicated list of all teams and saves per-season JSON + all_teams.json.

URL pattern: https://fbref.com/en/comps/26/YYYY-YYYY/YYYY-YYYY-Super-Lig-Stats

Using your FBRef login: Use your regular Chrome where you're already logged in:
  1. Close all Chrome windows.
  2. Run: python scripts/fetch_super_lig_standings.py --use-chrome
  The script will open Chrome with your profile (FBRef/Google login already there).
Alternatively use --chrome-user-data PATH to point to your Chrome User Data folder.

Requires: pip install playwright beautifulsoup4 pandas && playwright install chromium
"""
import argparse
import json
import os
import re
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit("Install Playwright: pip install playwright && playwright install chromium")

from bs4 import BeautifulSoup

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output", "super_lig")
SEASONS_DIR = os.path.join(OUTPUT_DIR, "seasons")
# Persistent browser profile: keeps cookies/login so FBRef doesn't show Cloudflare when logged in
DEFAULT_PROFILE_DIR = os.path.join(OUTPUT_DIR, "browser_profile")
# Default Chrome user data dir on Windows (use with --chrome-user-data to use your logged-in Chrome)
def _default_chrome_user_data():
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        return os.path.join(localappdata, "Google", "Chrome", "User Data")
    return ""
DEFAULT_CHROME_USER_DATA = _default_chrome_user_data()
BASE_URL = "https://fbref.com/en/comps/26/{season}/{season}-Super-Lig-Stats"
# FBRef shows Cloudflare briefly then loads; wait ~10s after opening page before scraping
SLEEP_AFTER_CLOUDFLARE = 10
WAIT_FOR_TABLE_TIMEOUT = 30_000

# Season range: 2001-2002 to 2024-2025 (2025-2026 not finished)
FIRST_SEASON = "2001-2002"
LAST_SEASON = "2024-2025"


def _parse_int(text: str) -> int:
    if text is None:
        return 0
    t = str(text).strip().replace(",", "")
    if t in ("", "-", "—"):
        return 0
    try:
        return int(t)
    except ValueError:
        return 0


def _season_years(season_slug: str) -> tuple[int, int]:
    """e.g. '2001-2002' -> (2001, 2002)."""
    m = re.match(r"(\d{4})-(\d{2,4})", season_slug)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y2 < 100:
            y2 += 2000 if y2 < 50 else 1900
        return (y1, y2)
    return (0, 0)


def get_season_slugs(start: str, end: str) -> list[str]:
    """Generate season slugs from start to end inclusive. e.g. 2001-2002, 2002-2003, ..."""
    y1_start, y2_start = _season_years(start)
    y1_end, y2_end = _season_years(end)
    slugs = []
    y1, y2 = y1_start, y2_start
    while (y1, y2) <= (y1_end, y2_end):
        slugs.append(f"{y1}-{y2}")
        y1 += 1
        y2 += 1
    return slugs


def get_page_url(season: str) -> str:
    return BASE_URL.format(season=season)


def find_standings_table(soup: BeautifulSoup):
    """Find the main league standings table. FBRef may use table id with 'results' or we match by thead content."""
    # Try by id (FBRef often uses results...overall or similar)
    for t in soup.find_all("table", id=True):
        if "result" in t.get("id", "").lower() and "overall" in t.get("id", "").lower():
            return t
    for t in soup.find_all("table", id=True):
        if "standings" in t.get("id", "").lower() or "results" in t.get("id", "").lower():
            return t
    # Fallback: any table whose thead mentions Squad and Pts/MP
    for table in soup.find_all("table"):
        thead = table.find("thead")
        if not thead:
            continue
        header_text = thead.get_text().lower()
        has_squad = "squad" in header_text or "team" in header_text
        has_stats = ("pts" in header_text or "mp" in header_text or "matches" in header_text or
                     ("w" in header_text and "d" in header_text and "l" in header_text))
        if has_squad and has_stats:
            return table
    return None


def _header_key(text: str) -> str:
    """Map header cell text to our key. Empty if not a stat we need."""
    t = (text or "").strip().lower()
    if t in ("", "stats", "overall", "performance", "playing time"):
        return ""
    if "squad" in t or t == "team":
        return "squad"
    if t in ("rk", "rank", "#", "r"):
        return "rank"
    if t in ("mp", "matches", "mat", "games", "gp"):
        return "mp"
    if t in ("w", "wins"):
        return "w"
    if t in ("d", "draws"):
        return "d"
    if t in ("l", "losses"):
        return "l"
    if t in ("gf", "goals for", "goals", "f"):
        return "gf"
    if t in ("ga", "goals against", "a"):
        return "ga"
    if t in ("gd", "diff", "goal diff", "goal difference"):
        return "gd"
    if t in ("pts", "points", "pt", "p"):
        return "pts"
    if "note" in t or "qual" in t:
        return "notes"
    return ""


def extract_standings(html: str, season: str) -> list[dict]:
    """
    Parse standings table. Returns list of team rows with:
    rank, team_name, team_id (slug), mp, w, d, l, gf, ga, gd, pts, notes, is_champion, relegated.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = find_standings_table(soup)
    if not table:
        return []

    thead = table.find("thead")
    tbody = table.find("tbody")
    if not thead or not tbody:
        return []

    # FBRef often has 2 header rows; use the last one for column keys
    header_rows = thead.find_all("tr")
    col_keys = []  # index -> key
    for tr in reversed(header_rows):
        for th in tr.find_all(["th", "td"]):
            key = _header_key(th.get_text() or "")
            col_keys.append(key)
        if col_keys:
            break
    if not col_keys:
        for i, th in enumerate(header_rows[-1].find_all(["th", "td"])) if header_rows else []:
            col_keys.append(_header_key(th.get_text() or "") or f"col_{i}")

    # Build index -> key map (only for keys we care about)
    col_map = {}
    for i, key in enumerate(col_keys):
        if key and key != "":
            col_map[i] = key

    rows = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        team_name = ""
        team_id = ""
        rank = 0
        mp = w = d = l = gf = ga = gd = pts = 0
        notes = ""

        for i, cell in enumerate(cells):
            if i not in col_map:
                continue
            key = col_map[i]
            text = (cell.get_text() or "").strip()
            if key == "rank":
                rank = _parse_int(text)
            elif key == "squad":
                team_name = text
                a = cell.find("a", href=re.compile(r"/squads/|/teams/"))
                if a and a.get("href"):
                    parts = [p for p in a["href"].rstrip("/").split("/") if p]
                    # FBRef: /en/squads/abc123/Club-Name -> use abc123 if alphanumeric, else Club-Name slug
                    if len(parts) >= 2 and re.match(r"^[a-zA-Z0-9]+$", parts[-2]):
                        team_id = parts[-2]
                    else:
                        team_id = re.sub(r"[^a-z0-9]+", "-", (parts[-1] if parts else "").lower()).strip("-")
                if not team_id and team_name:
                    team_id = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")
            elif key == "mp":
                mp = _parse_int(text)
            elif key == "w":
                w = _parse_int(text)
            elif key == "d":
                d = _parse_int(text)
            elif key == "l":
                l = _parse_int(text)
            elif key == "gf":
                gf = _parse_int(text)
            elif key == "ga":
                ga = _parse_int(text)
            elif key == "gd":
                gd = _parse_int(text)
            elif key == "pts":
                pts = _parse_int(text)
            elif key == "notes":
                notes = text

        if not team_name:
            continue
        if not team_id:
            team_id = re.sub(r"[^a-z0-9]+", "-", team_name.lower()).strip("-")

        row = {
            "rank": rank,
            "team_name": team_name,
            "team_id": team_id,
            "mp": mp,
            "w": w,
            "d": d,
            "l": l,
            "gf": gf,
            "ga": ga,
            "gd": gd,
            "pts": pts,
            "notes": notes,
        }
        # Champion = 1st place; relegated from notes
        if rank == 1:
            row["is_champion"] = True
        if notes and "relegat" in notes.lower():
            row["relegated"] = True
        rows.append(row)

    # Fallback: try pandas read_html (handles multi-level columns)
    if not rows and HAS_PANDAS:
        try:
            import io
            dfs = pd.read_html(io.StringIO(html))
            for df in dfs:
                if df.empty or len(df) < 5:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.copy()
                    df.columns = [str(c[-1]) if c[-1] else "_".join(str(x) for x in c) for c in df.columns]
                cols_str = [str(c).lower() for c in df.columns]
                has_squad = any("squad" in s or "team" in s for s in cols_str)
                has_pts = any("pts" in s or "points" in s or "mp" in s for s in cols_str)
                if not (has_squad and has_pts):
                    continue
                squad_col = next((c for c in df.columns if "squad" in str(c).lower() or "team" in str(c).lower()), None)
                if squad_col is None:
                    continue
                for _, r in df.iterrows():
                    name = str(r.get(squad_col, "")).strip()
                    if not name or name == "nan" or len(name) < 2:
                        continue
                    team_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                    def get_col(*keys):
                        for k in keys:
                            for c in df.columns:
                                if k.lower() in str(c).lower():
                                    return r.get(c, 0)
                        return 0
                    row = {
                        "rank": _parse_int(get_col("Rk", "Rank", "#")),
                        "team_name": name,
                        "team_id": team_id,
                        "mp": _parse_int(get_col("MP", "Matches", "Mat")),
                        "w": _parse_int(get_col("W")),
                        "d": _parse_int(get_col("D", "Draws")),
                        "l": _parse_int(get_col("L", "Losses")),
                        "gf": _parse_int(get_col("GF", "Goals")),
                        "ga": _parse_int(get_col("GA")),
                        "gd": _parse_int(get_col("GD", "Diff")),
                        "pts": _parse_int(get_col("Pts", "PTS", "Points")),
                        "notes": str(r.get("Notes", r.get("Qualification", "")) or "").strip(),
                    }
                    if row["rank"] == 1:
                        row["is_champion"] = True
                    if row["notes"] and "relegat" in row["notes"].lower():
                        row["relegated"] = True
                    rows.append(row)
                if rows:
                    break
        except Exception:
            pass
    return rows


def slug_from_team(team_name: str, team_id: str) -> str:
    """Stable id for dedup: prefer team_id from URL, else slug from name."""
    if team_id:
        return team_id
    return re.sub(r"[^a-z0-9]+", "-", (team_name or "").lower()).strip("-") or "unknown"


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Super Lig standings from FBRef (2001-2002 to 2024-2025)."
    )
    parser.add_argument(
        "--start",
        default=FIRST_SEASON,
        help=f"First season e.g. {FIRST_SEASON}",
    )
    parser.add_argument(
        "--end",
        default=LAST_SEASON,
        help=f"Last season e.g. {LAST_SEASON}",
    )
    parser.add_argument("--debug", action="store_true", help="Save HTML to output dir when no table found")
    parser.add_argument("--headed", action="store_true", help="Run browser visible (for first-time login)")
    parser.add_argument(
        "--profile-dir",
        default=DEFAULT_PROFILE_DIR,
        help="Persistent browser profile path (saves FBRef login; default: output/football/super_lig/browser_profile)",
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Do not use a persistent profile (default is to use one so your login is reused)",
    )
    parser.add_argument(
        "--use-chrome",
        action="store_true",
        help="Use your installed Chrome and its profile (you stay logged in to FBRef/Google). "
        "Close all Chrome windows before running.",
    )
    parser.add_argument(
        "--chrome-user-data",
        default=None,
        metavar="PATH",
        help="Chrome User Data folder path (default with --use-chrome: %%LOCALAPPDATA%%\\Google\\Chrome\\User Data). "
        "Close all Chrome windows before running.",
    )
    args = parser.parse_args()

    seasons = get_season_slugs(args.start, args.end)
    os.makedirs(SEASONS_DIR, exist_ok=True)

    all_teams_by_id = {}  # team_id -> { id, name, first_season, last_season }

    chrome_user_data = None
    if args.use_chrome:
        chrome_user_data = args.chrome_user_data or DEFAULT_CHROME_USER_DATA
        if not chrome_user_data or not os.path.isdir(chrome_user_data):
            raise SystemExit(
                "Chrome profile not found. Install Chrome or pass --chrome-user-data PATH to your User Data folder."
            )
        print("Using your Chrome profile. Close all Chrome windows before running.")
    elif args.chrome_user_data:
        chrome_user_data = args.chrome_user_data
        if not os.path.isdir(chrome_user_data):
            raise SystemExit(f"Chrome User Data folder not found: {chrome_user_data}")
        print(f"Using Chrome profile: {chrome_user_data}")
        print("Close all Chrome windows before running.")

    use_profile = not args.no_profile
    profile_dir = args.profile_dir if use_profile else None
    if use_profile and not chrome_user_data:
        os.makedirs(profile_dir, exist_ok=True)
        print(f"Using browser profile: {profile_dir}")
        print("(Log in to FBRef in the opened browser if needed; session will be saved for next runs.)")

    with sync_playwright() as p:
        if chrome_user_data:
            # Use installed Chrome with your profile (FBRef/Google already logged in)
            context = p.chromium.launch_persistent_context(
                chrome_user_data,
                channel="chrome",
                headless=False,  # Chrome profile often needs visible window
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                accept_downloads=False,
            )
            try:
                page = context.new_page()
                page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

                for season in seasons:
                    url = get_page_url(season)
                    print(f"[{season}] Loading {url} ...")
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    except Exception as e:
                        print(f"[{season}] Load failed: {e}")
                        continue
                    print(f"[{season}] Waiting {SLEEP_AFTER_CLOUDFLARE}s for page to load ...")
                    time.sleep(SLEEP_AFTER_CLOUDFLARE)
                    try:
                        page.wait_for_selector("table", timeout=WAIT_FOR_TABLE_TIMEOUT)
                    except Exception:
                        pass
                    time.sleep(1)
                    html = page.content()
                    rows = extract_standings(html, season)
                    if not rows:
                        print(f"[{season}] No standings table found.")
                        if args.debug:
                            debug_path = os.path.join(OUTPUT_DIR, f"debug_{season.replace('-', '_')}.html")
                            with open(debug_path, "w", encoding="utf-8") as f:
                                f.write(html)
                            print(f"[{season}] Saved HTML to {debug_path}")
                        continue
                    for r in rows:
                        tid = slug_from_team(r["team_name"], r.get("team_id") or "")
                        if tid not in all_teams_by_id:
                            all_teams_by_id[tid] = {
                                "id": tid,
                                "name": r["team_name"],
                                "first_season": season,
                                "last_season": season,
                            }
                        else:
                            all_teams_by_id[tid]["name"] = r["team_name"]
                            if season < all_teams_by_id[tid]["first_season"]:
                                all_teams_by_id[tid]["first_season"] = season
                            if season > all_teams_by_id[tid]["last_season"]:
                                all_teams_by_id[tid]["last_season"] = season

                    season_data = {
                        "season": season,
                        "standings": rows,
                    }
                    season_path = os.path.join(SEASONS_DIR, f"{season.replace('-', '_')}.json")
                    with open(season_path, "w", encoding="utf-8") as f:
                        json.dump(season_data, f, ensure_ascii=False, indent=2)
                    print(f"[{season}] Saved {len(rows)} teams -> {season_path}")

            finally:
                context.close()
        elif use_profile and profile_dir:
            context = p.chromium.launch_persistent_context(
                profile_dir,
                headless=not args.headed,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                accept_downloads=False,
            )
            try:
                page = context.new_page()
                page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

                for season in seasons:
                    url = get_page_url(season)
                    print(f"[{season}] Loading {url} ...")
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    except Exception as e:
                        print(f"[{season}] Load failed: {e}")
                        continue
                    # Cloudflare overlay disappears after a few seconds; wait before fetching
                    print(f"[{season}] Waiting {SLEEP_AFTER_CLOUDFLARE}s for page to load ...")
                    time.sleep(SLEEP_AFTER_CLOUDFLARE)
                    # Optionally wait for standings table to appear
                    try:
                        page.wait_for_selector("table", timeout=WAIT_FOR_TABLE_TIMEOUT)
                    except Exception:
                        pass
                    time.sleep(1)
                    html = page.content()
                    rows = extract_standings(html, season)
                    if not rows:
                        print(f"[{season}] No standings table found.")
                        if args.debug:
                            debug_path = os.path.join(OUTPUT_DIR, f"debug_{season.replace('-', '_')}.html")
                            with open(debug_path, "w", encoding="utf-8") as f:
                                f.write(html)
                            print(f"[{season}] Saved HTML to {debug_path}")
                        continue
                    for r in rows:
                        tid = slug_from_team(r["team_name"], r.get("team_id") or "")
                        if tid not in all_teams_by_id:
                            all_teams_by_id[tid] = {
                                "id": tid,
                                "name": r["team_name"],
                                "first_season": season,
                                "last_season": season,
                            }
                        else:
                            all_teams_by_id[tid]["name"] = r["team_name"]
                            if season < all_teams_by_id[tid]["first_season"]:
                                all_teams_by_id[tid]["first_season"] = season
                            if season > all_teams_by_id[tid]["last_season"]:
                                all_teams_by_id[tid]["last_season"] = season

                    season_data = {
                        "season": season,
                        "standings": rows,
                    }
                    season_path = os.path.join(SEASONS_DIR, f"{season.replace('-', '_')}.json")
                    with open(season_path, "w", encoding="utf-8") as f:
                        json.dump(season_data, f, ensure_ascii=False, indent=2)
                    print(f"[{season}] Saved {len(rows)} teams -> {season_path}")

            finally:
                context.close()
        else:
            browser = p.chromium.launch(headless=not args.headed)
            try:
                page = browser.new_page()
                page.set_viewport_size({"width": 1280, "height": 900})
                page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

                for season in seasons:
                    url = get_page_url(season)
                    print(f"[{season}] Loading {url} ...")
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    except Exception as e:
                        print(f"[{season}] Load failed: {e}")
                        continue
                    print(f"[{season}] Waiting {SLEEP_AFTER_CLOUDFLARE}s for page to load ...")
                    time.sleep(SLEEP_AFTER_CLOUDFLARE)
                    try:
                        page.wait_for_selector("table", timeout=WAIT_FOR_TABLE_TIMEOUT)
                    except Exception:
                        pass
                    time.sleep(1)
                    html = page.content()
                    rows = extract_standings(html, season)
                    if not rows:
                        print(f"[{season}] No standings table found.")
                        if args.debug:
                            debug_path = os.path.join(OUTPUT_DIR, f"debug_{season.replace('-', '_')}.html")
                            with open(debug_path, "w", encoding="utf-8") as f:
                                f.write(html)
                            print(f"[{season}] Saved HTML to {debug_path}")
                        continue
                    for r in rows:
                        tid = slug_from_team(r["team_name"], r.get("team_id") or "")
                        if tid not in all_teams_by_id:
                            all_teams_by_id[tid] = {
                                "id": tid,
                                "name": r["team_name"],
                                "first_season": season,
                                "last_season": season,
                            }
                        else:
                            all_teams_by_id[tid]["name"] = r["team_name"]
                            if season < all_teams_by_id[tid]["first_season"]:
                                all_teams_by_id[tid]["first_season"] = season
                            if season > all_teams_by_id[tid]["last_season"]:
                                all_teams_by_id[tid]["last_season"] = season

                    season_data = {
                        "season": season,
                        "standings": rows,
                    }
                    season_path = os.path.join(SEASONS_DIR, f"{season.replace('-', '_')}.json")
                    with open(season_path, "w", encoding="utf-8") as f:
                        json.dump(season_data, f, ensure_ascii=False, indent=2)
                    print(f"[{season}] Saved {len(rows)} teams -> {season_path}")

            finally:
                browser.close()

    # Save unique teams (sorted by name)
    teams_list = sorted(all_teams_by_id.values(), key=lambda x: (x["name"].lower(), x["id"]))
    teams_path = os.path.join(OUTPUT_DIR, "all_teams.json")
    with open(teams_path, "w", encoding="utf-8") as f:
        json.dump(teams_list, f, ensure_ascii=False, indent=2)
    print(f"\nDone. {len(teams_list)} unique teams -> {teams_path}")


if __name__ == "__main__":
    main()
