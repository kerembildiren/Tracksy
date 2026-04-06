"""
Fetch NBA triple-doubles by season from Land of Basketball and merge into allplayers.json.
Uses same year range as 30+ games (2026 down to 1980). Adds/updates "triple_doubles" per player.
Prints fetched data to console for each year.

URL: https://www.landofbasketball.com/year_by_year_stats/{start}_{end}_triple_doubles_rs.htm
e.g. 2025-26 season -> 2025_2026_triple_doubles_rs.htm

Requires: pip install playwright beautifulsoup4 && playwright install chromium
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output")
ALLPLAYERS_FILE = "allplayers.json"
BASE_URL = "https://www.landofbasketball.com/year_by_year_stats/{start}_{end}_triple_doubles_rs.htm"
PLAYER_LINK_PATTERN = re.compile(r"nba_players/[^/]+\.htm")
MORE_LINK_TEXT = "more >>"
MAX_MORE_CLICKS = 50
SLEEP_AFTER_LOAD = 2.0
SLEEP_AFTER_CLICK = 1.0


def get_page_url(year: int) -> str:
    """Season ending in year -> e.g. 2026 -> 2025_2026."""
    return BASE_URL.format(start=year - 1, end=year)


def extract_triple_doubles(html: str) -> list[dict]:
    """
    Parse HTML: rows with player link; Triple-Doubles count is third column (index 2).
    Returns list of {"id": name, "triple_doubles": int}.
    """
    soup = BeautifulSoup(html, "html.parser")
    records = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            player_a = tr.find("a", href=lambda h: h and PLAYER_LINK_PATTERN.search(h))
            if not player_a:
                continue
            name = (player_a.get_text() or "").strip()
            if not name:
                continue
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            val = (cells[2].get_text() or "").strip()
            if not val.isdigit():
                continue
            records.append({"id": name, "triple_doubles": int(val)})

    return records


def load_allplayers(path: str) -> dict[str, dict]:
    """Load allplayers.json; ensure id, 30plus_games, 40plus_games, triple_doubles."""
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for item in raw:
        name = (item.get("id") or "").strip()
        if not name:
            continue
        out[name] = {
            "id": name,
            "30plus_games": int(item.get("30plus_games") or 0),
            "40plus_games": int(item.get("40plus_games") or 0),
            "triple_doubles": int(item.get("triple_doubles") or 0),
        }
    return out


def save_allplayers(path: str, players: dict[str, dict]) -> None:
    """Write allplayers.json with all fields, sorted by 30plus_games descending."""
    list_ = sorted(players.values(), key=lambda x: (-x["30plus_games"], x["id"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list_, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch triple-doubles by year and update allplayers.json (career totals)."
    )
    parser.add_argument("--start-year", type=int, default=2026, help="First season year (default 2026)")
    parser.add_argument("--end-year", type=int, default=1980, help="Last season year (default 1980)")
    args = parser.parse_args()

    start_year = max(args.start_year, args.end_year)
    end_year = min(args.start_year, args.end_year)
    years = list(range(start_year, end_year - 1, -1))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, ALLPLAYERS_FILE)
    players = load_allplayers(out_path)
    # Ensure triple_doubles exists for all
    for p in players.values():
        if "triple_doubles" not in p:
            p["triple_doubles"] = 0

    print(f"Loaded {len(players)} players from {ALLPLAYERS_FILE}.")
    print(f"Fetching triple-doubles for seasons: {years}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 900})

            for year in years:
                url = get_page_url(year)
                print(f"[{year}] Loading {url} ...")
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                time.sleep(SLEEP_AFTER_LOAD)

                for _ in range(MAX_MORE_CLICKS):
                    try:
                        more = page.get_by_text(MORE_LINK_TEXT, exact=True).first
                        if more.is_visible(timeout=2000):
                            more.click()
                            time.sleep(SLEEP_AFTER_CLICK)
                        else:
                            break
                    except Exception:
                        break

                html = page.content()
                records = extract_triple_doubles(html)
                print(f"[{year}] Parsed {len(records)} players with triple-doubles.")
                print(f"  Data fetched:")
                for r in records[:20]:
                    print(f"    {r['id']}: {r['triple_doubles']} triple-doubles")
                if len(records) > 20:
                    print(f"    ... and {len(records) - 20} more")
                print()

                added = 0
                for r in records:
                    name = r["id"]
                    if name not in players:
                        players[name] = {
                            "id": name,
                            "30plus_games": 0,
                            "40plus_games": 0,
                            "triple_doubles": 0,
                        }
                        added += 1
                    players[name]["triple_doubles"] += r["triple_doubles"]

                save_allplayers(out_path, players)
                print(f"[{year}] Merged. New players this year: {added}. Total in file: {len(players)}. Saved.\n")
        finally:
            browser.close()

    print(f"Done. {len(players)} players in {out_path}")


if __name__ == "__main__":
    main()
