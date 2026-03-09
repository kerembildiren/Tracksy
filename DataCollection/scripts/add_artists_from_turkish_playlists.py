"""
Add Turkish artists from specific playlists (all artists are Turkish).
Scrapes the playlist pages for artist IDs, fetches id+name from Spotify API for new
artists only, and appends them at the end of artists_raw.json. No re-sort, no
popularity assigned. Duplicates (already in JSON) are skipped.

Usage:
  1. Set credentials: $env:SPOTIPY_CLIENT_ID="..."; $env:SPOTIPY_CLIENT_SECRET="..."
  2. Run all 3 playlists:  python scripts/add_artists_from_turkish_playlists.py
  3. Run only 2nd playlist (194 songs):  python scripts/add_artists_from_turkish_playlists.py --only 2
  4. Run only 3rd playlist:  python scripts/add_artists_from_turkish_playlists.py --only 3

Requires: pip install playwright && playwright install chromium
"""
import argparse
import json
import os
import re
import time

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit("Install Playwright: pip install playwright && playwright install chromium")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output")
ARTISTS_FILE = "artists_raw.json"
PLAYLIST_URL = "https://open.spotify.com/playlist/{id}"
ARTIST_ID_PATTERN = re.compile(r"/artist/([a-zA-Z0-9]{22})")
SLEEP_API = 1.5
SLEEP_PLAYLIST = 2.0

# User-provided playlists (all Turkish artists)
PLAYLIST_IDS = [
    "1omvypNscvSlYjXs23GAct",  # Kero - Turkish classics
    "5pNNCxNEhl5tKxkI9kFAoW",  # Türkçe Pop Efsaneler
    "1dMywfUo5cRv8BSfUent8P",  # Türkçe '70'80'90 nostaljik
]


def require_env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise SystemExit(f"Missing {name}. Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET.")
    return v


def create_client() -> spotipy.Spotify:
    require_env("SPOTIPY_CLIENT_ID")
    require_env("SPOTIPY_CLIENT_SECRET")
    auth = SpotifyClientCredentials()
    return spotipy.Spotify(
        auth_manager=auth,
        requests_timeout=20,
        retries=6,
        status_forcelist=(429, 500, 502, 503, 504),
        backoff_factor=0.4,
    )


def get_playlist_artist_ids(
    playlist_id: str,
    *,
    max_scrolls: int = 200,
    scroll_pause: float = 0.7,
    max_no_new: int = 8,
    initial_sleep: float = 4.0,
) -> set[str]:
    """Scrape playlist page; scroll to load all tracks (Spotify lazy-loads), then extract all artist IDs."""
    url = PLAYLIST_URL.format(id=playlist_id)
    ids = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 900})
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(initial_sleep)

            # Viewport: 1280x900 - center (640, 450) is where the track list lives; scroll only works there
            center_x, center_y = 640, 450

            no_new_count = 0
            last_reported = 0

            for scroll_num in range(max_scrolls):
                content = page.content()
                prev_len = len(ids)
                ids |= set(ARTIST_ID_PATTERN.findall(content))

                if len(ids) > prev_len:
                    no_new_count = 0
                else:
                    no_new_count += 1

                if len(ids) >= last_reported + 15:
                    print(f"    ... {len(ids)} artists so far (scroll {scroll_num + 1})")
                    last_reported = len(ids)

                if no_new_count >= max_no_new:
                    print(f"    No new artists for {max_no_new} scrolls, stopping.")
                    break

                # Move mouse to CENTER of screen so wheel scroll hits the track list (not left/right panels)
                page.mouse.move(center_x, center_y)
                time.sleep(0.15)
                page.mouse.wheel(0, 500)
                time.sleep(scroll_pause)

        finally:
            browser.close()
    return ids


def fetch_artist(sp: spotipy.Spotify, artist_id: str) -> dict | None:
    try:
        return sp.artist(artist_id)
    except SpotifyException:
        return None


def minimal_record(api_artist: dict) -> dict:
    """Our JSON format with only id and name set; no popularity."""
    return {
        "id": api_artist["id"],
        "name": api_artist["name"],
        "gender": None,
        "genres": api_artist.get("genres") or [],
        "popularity": None,
        "debut": None,
        "nationality": "Turkey",
        "group_size": 1,
        "spotify_monthly_streams": None,
        "image_url": None,
        "top_track_name": None,
        "top_track_uri": None,
        "top_track_id": None,
    }


def main():
    parser = argparse.ArgumentParser(description="Add Turkish artists from playlists to artists_raw.json")
    parser.add_argument(
        "--only",
        type=int,
        choices=[1, 2, 3],
        help="Run only this playlist (1=first, 2=second ~194 songs, 3=third). Slower, thorough scroll.",
    )
    args = parser.parse_args()

    path = os.path.join(OUTPUT_DIR, ARTISTS_FILE)
    if not os.path.isfile(path):
        raise SystemExit(f"Not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    existing_ids = {a["id"] for a in artists}

    if args.only:
        playlist_ids = [PLAYLIST_IDS[args.only - 1]]
        # Thorough scroll for single-playlist run (e.g. 194 tracks)
        scroll_opts = dict(
            max_scrolls=400,
            scroll_pause=1.0,
            max_no_new=15,
            initial_sleep=5.0,
        )
        print(f"Running only playlist {args.only} (thorough scroll, may take several minutes).\n")
    else:
        playlist_ids = PLAYLIST_IDS
        scroll_opts = {}

    all_ids = set()
    for pid in playlist_ids:
        print(f"Scraping playlist {pid}...")
        try:
            ids = get_playlist_artist_ids(pid, **scroll_opts)
            all_ids |= ids
            print(f"  -> {len(ids)} artists. Total unique so far: {len(all_ids)}")
        except Exception as e:
            print(f"  -> Error: {e}. Skipped.")
        time.sleep(SLEEP_PLAYLIST)

    missing_ids = [aid for aid in all_ids if aid not in existing_ids]
    print(f"\nAlready in DB: {len(all_ids) - len(missing_ids)}. To add: {len(missing_ids)}.")

    if not missing_ids:
        print("Nothing new to add.")
        return

    sp = create_client()
    added = []
    for i, aid in enumerate(missing_ids):
        if i > 0:
            time.sleep(SLEEP_API)
        try:
            api_artist = fetch_artist(sp, aid)
        except SpotifyException as e:
            if e.http_status == 429:
                ra = int((e.headers or {}).get("Retry-After", 60))
                print(f"Rate limited. Wait {ra}s. Re-run to resume.")
                break
            continue
        if not api_artist:
            continue
        record = minimal_record(api_artist)
        artists.append(record)
        existing_ids.add(aid)
        added.append(record["name"])
        print(f"  Added: {record['name']} ({aid})")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Appended {len(added)} new artist(s) at the end. Total in file: {len(artists)}.")
    print("Next: run update_artists_spotify_streams.py to fetch monthly streams for new artists.")


if __name__ == "__main__":
    main()
