"""
Fetch NBA players 30+ and 40+ point games from Land of Basketball (regular season).
Updates allplayers.json with career totals: for each year 2026 down to 1980, adds
that season's 30plus_games and 40plus_games (40+ = 40-49 + 50-59 + 60-69 + 70+).
Saves after each year and prints progress. Output is sorted by 30plus_games (highest first).

URL: https://www.landofbasketball.com/year_by_year_points/{YEAR}_30_point_games_rs.htm

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
BASE_URL = "https://www.landofbasketball.com/year_by_year_points/{year}_30_point_games_rs.htm"
PLAYER_LINK_PATTERN = re.compile(r"nba_players/[^/]+\.htm")
MORE_LINK_TEXT = "more >>"
MAX_MORE_CLICKS = 50
SLEEP_AFTER_LOAD = 2.0
SLEEP_AFTER_CLICK = 1.0
# Points Details columns: 30-39, 40-49, 50-59, 60-69, 70+ (indices 5-9); 40+ = 6+7+8+9
IDX_40_49, IDX_50_59, IDX_60_69, IDX_70_PLUS = 6, 7, 8, 9


def _parse_int_cell(text: str) -> int:
    t = (text or "").strip()
    if t == "" or t == "-":
        return 0
    return int(t) if t.isdigit() else 0


def get_page_url(year: int) -> str:
    return BASE_URL.format(year=year)


def extract_players_and_counts(html: str) -> list[dict]:
    """
    Parse HTML: each row has player name, 30+ games, and Points Details (30-39, 40-49, 50-59, 60-69, 70+).
    Returns list of {"id": name, "30plus_games": int, "40plus_games": int}.
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
            if len(cells) <= IDX_70_PLUS:
                continue
            val_30 = (cells[2].get_text() or "").strip()
            if not val_30.isdigit():
                continue
            thirty_plus = int(val_30)
            forty_plus = (
                _parse_int_cell(cells[IDX_40_49].get_text())
                + _parse_int_cell(cells[IDX_50_59].get_text())
                + _parse_int_cell(cells[IDX_60_69].get_text())
                + _parse_int_cell(cells[IDX_70_PLUS].get_text())
            )
            records.append({"id": name, "30plus_games": thirty_plus, "40plus_games": forty_plus})

    return records


def load_allplayers(path: str) -> dict[str, dict]:
    """Load allplayers.json; return dict by id. Ensure 30plus_games, 40plus_games, triple_doubles exist."""
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
    """Write allplayers.json with all fields, sorted by 30plus_games descending (highest first), then id."""
    list_ = sorted(players.values(), key=lambda x: (-x["30plus_games"], x["id"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list_, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch 30+ and 40+ point games by year; update allplayers.json (career totals)."
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2026,
        help="First season year (default 2026)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=1980,
        help="Last season year (default 1980)",
    )
    args = parser.parse_args()

    start_year = max(args.start_year, args.end_year)
    end_year = min(args.start_year, args.end_year)
    years = list(range(start_year, end_year - 1, -1))  # e.g. 2026 down to 1980

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, ALLPLAYERS_FILE)
    players = load_allplayers(out_path)
    print(f"Loaded {len(players)} players from {ALLPLAYERS_FILE} (or starting fresh).")
    print(f"Fetching years: {years}\n")

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
                records = extract_players_and_counts(html)
                print(f"[{year}] Parsed {len(records)} players.")

                added, updated = 0, 0
                for r in records:
                    name = r["id"]
                    if name not in players:
                        players[name] = {"id": name, "30plus_games": 0, "40plus_games": 0, "triple_doubles": 0}
                        added += 1
                    players[name]["30plus_games"] += r["30plus_games"]
                    players[name]["40plus_games"] += r["40plus_games"]
                    updated += 1

                save_allplayers(out_path, players)
                print(f"[{year}] Merged (new this year: {added}). Total players: {len(players)}. Saved to {ALLPLAYERS_FILE}.\n")
        finally:
            browser.close()

    print(f"Done. {len(players)} players in {out_path}")


if __name__ == "__main__":
    main()
