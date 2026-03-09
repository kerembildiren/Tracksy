"""
Fetch Spotify monthly listeners (monthly streams) by opening each artist page in a
real browser so the value is visible after JavaScript runs. No Spotify API needed.

Flow: for each artist in artists_raw.json we open https://open.spotify.com/artist/{id},
wait for the page to render, then read the "X monthly listeners" text and store it
in a new field: spotify_monthly_streams.

Requires: pip install playwright && playwright install chromium

Usage:
  python update_artists_spotify_streams.py                    # all artists missing spotify_monthly_streams
  python update_artists_spotify_streams.py --test             # only Tarkan, Sezen Aksu, Semicenk (dry run)
  python update_artists_spotify_streams.py --start-after Joker # only artists after Joker in the JSON (e.g. playlist-added ones)
"""

import argparse
import json
import os
import re
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit(
        "Install Playwright: pip install playwright\n"
        "Then install browser: playwright install chromium"
    )

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output")
INPUT_OUTPUT_FILE = "artists_raw.json"
SPOTIFY_ARTIST_URL = "https://open.spotify.com/artist/{id}"
# Wait for the "monthly listeners" line to appear (JS-rendered)
WAIT_FOR_SELECTOR = "text=monthly listeners"
WAIT_TIMEOUT_MS = 15_000
# After page load, short delay so numbers are painted
EXTRA_WAIT_AFTER_LOAD_S = 1.5
SAVE_EVERY_N = 20
# Delay between artists to avoid hammering
SLEEP_BETWEEN_ARTISTS = 2.0


def _parse_monthly_listeners_from_text(text: str) -> int | None:
    """Extract the number from text like '4,827,069 monthly listeners'."""
    if not text:
        return None
    m = re.search(r"([\d,]+)\s*monthly\s*listeners", text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).replace(",", "").strip()
    try:
        return int(raw)
    except ValueError:
        return None


def fetch_monthly_streams_with_browser(page, artist_id: str) -> int | None:
    """
    Open the artist page in the given Playwright page, wait for content, return
    monthly listeners count or None.
    """
    url = SPOTIFY_ARTIST_URL.format(id=artist_id)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=WAIT_TIMEOUT_MS)
        # Wait until the "monthly listeners" text is visible (JS has run)
        page.wait_for_selector(WAIT_FOR_SELECTOR, timeout=WAIT_TIMEOUT_MS)
        time.sleep(EXTRA_WAIT_AFTER_LOAD_S)
        body_text = page.inner_text("body")
        return _parse_monthly_listeners_from_text(body_text)
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Spotify monthly streams via browser.")
    parser.add_argument("--test", action="store_true", help="Only fetch Tarkan, Sezen Aksu, Semicenk and print values (no JSON write).")
    parser.add_argument("--start-after", metavar="NAME", help="Only process artists that appear after this artist name in the JSON (e.g. Joker). Use for playlist-added artists only.")
    args = parser.parse_args()

    path = os.path.join(OUTPUT_DIR, INPUT_OUTPUT_FILE)
    if not os.path.isdir(OUTPUT_DIR):
        raise SystemExit(f"Output directory not found: {OUTPUT_DIR}")

    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    if not artists:
        print("No artists in file. Exiting.")
        return

    start_index = 0
    if args.start_after:
        name = args.start_after.strip()
        found = None
        for i, a in enumerate(artists):
            if (a.get("name") or "").strip() == name:
                found = i
        if found is None:
            raise SystemExit(f"Artist '{name}' not found in JSON.")
        start_index = found + 1
        print(f"Processing only artists after '{name}' (from index {start_index} to end).\n")

    if args.test:
        test_names = {"Tarkan", "Sezen Aksu", "Semicenk"}
        to_fetch = [(i, a) for i, a in enumerate(artists) if a.get("name") in test_names]
        if not to_fetch:
            print("Test artists not found in JSON.")
            return
        print("Test run: fetching monthly streams for Tarkan, Sezen Aksu, Semicenk (no file write).\n")
    else:
        to_fetch = [
            (i, a) for i, a in enumerate(artists)
            if i >= start_index and a.get("spotify_monthly_streams") is None
        ]
        if not to_fetch:
            print("No artists to fetch (all in range already have spotify_monthly_streams).")
            return

    total = len(to_fetch)
    print(f"Fetching spotify_monthly_streams for {total} artists (browser-based).")

    updated = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            # Realistic viewport and user agent
            page.set_viewport_size({"width": 1280, "height": 720})
            page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
            })

            for k, (idx, artist) in enumerate(to_fetch):
                aid = (artist.get("id") or "").strip()
                if not aid:
                    artist["spotify_monthly_streams"] = None
                else:
                    value = fetch_monthly_streams_with_browser(page, aid)
                    artist["spotify_monthly_streams"] = value
                    if value is not None:
                        updated += 1
                        print(f"  {artist.get('name', '?')}: {value:,}")

                time.sleep(SLEEP_BETWEEN_ARTISTS)

                if not args.test and ((k + 1) % SAVE_EVERY_N == 0 or (k + 1) == total):
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(artists, f, ensure_ascii=False, indent=2)
                    print(f"  Progress: {k + 1}/{total} (saved), found: {updated}")
        finally:
            browser.close()

    if args.test:
        print("\nTest done. Run without --test to update the JSON for all artists.")
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)
    print(f"Done. spotify_monthly_streams set for {updated}/{total} artists. Saved to {path}")


if __name__ == "__main__":
    main()
