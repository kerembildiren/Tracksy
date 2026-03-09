"""
Discover Turkish artists that are NOT in our database by reading Spotify's
Turkey chart playlists (Top 50, Viral 50, etc.). All unique artist IDs from
those playlists are collected; any ID that isn't already in artists_raw.json
is fetched from the API and added (no duplicates).

Playlist tracks require user auth in the API, so we use Playwright to scrape
the playlist page for artist links instead. Artist details are then fetched
with the API (client credentials).

Requires: pip install playwright && playwright install chromium

Usage:
  1. Set credentials (for fetching artist details):
       $env:SPOTIPY_CLIENT_ID="..."
       $env:SPOTIPY_CLIENT_SECRET="..."
  2. Run (uses default Turkey playlists):
       python scripts/discover_artists_from_playlists.py
  3. Or pass custom playlist IDs:
       python scripts/discover_artists_from_playlists.py 37i9dQZEVXbIVYVBNw9D5K

After running: run update_artists_spotify_streams.py to get monthly streams
for new artists, then tidy_artists_json.py to re-sort by streams.
"""
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
SLEEP_BETWEEN_REQUESTS = 1.5
NATIONALITY = "Turkey"
PLAYLIST_URL = "https://open.spotify.com/playlist/{id}"
# Spotify artist IDs are 22 characters
ARTIST_ID_PATTERN = re.compile(r"/artist/([a-zA-Z0-9]{22})")

# Official Spotify playlists for Turkey (most streamed / viral tracks → we get artists)
DEFAULT_PLAYLIST_IDS = [
    "37i9dQZEVXbIVYVBNw9D5K",  # Top 50 - Turkey
    "2gvAEDq8Bx4nZezuSGBawF",  # Viral 50 - Turkey
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


def get_playlist_artist_ids_with_browser(playlist_id: str) -> set[str]:
    """Scrape playlist page with Playwright; extract artist IDs from links. No user auth needed."""
    url = PLAYLIST_URL.format(id=playlist_id)
    ids = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            # Wait for track rows / content to render
            page.wait_for_load_state("networkidle", timeout=15_000)
            time.sleep(2.0)
            content = page.content()
            ids = set(ARTIST_ID_PATTERN.findall(content))
        finally:
            browser.close()
    return ids


def fetch_artist(sp: spotipy.Spotify, artist_id: str) -> dict | None:
    try:
        return sp.artist(artist_id)
    except SpotifyException:
        return None


def api_artist_to_record(api_artist: dict) -> dict:
    images = api_artist.get("images") or []
    image_url = images[0]["url"] if images and images[0].get("url") else None
    return {
        "id": api_artist["id"],
        "name": api_artist["name"],
        "gender": None,
        "genres": api_artist.get("genres") or [],
        "popularity": 0,
        "debut": None,
        "nationality": NATIONALITY,
        "group_size": 1,
        "spotify_monthly_streams": None,
        "image_url": image_url,
        "top_track_name": None,
        "top_track_uri": None,
        "top_track_id": None,
    }


def main():
    import sys
    playlist_ids = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_PLAYLIST_IDS

    path = os.path.join(OUTPUT_DIR, ARTISTS_FILE)
    if not os.path.isfile(path):
        raise SystemExit(f"Not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    existing_ids = {a["id"] for a in artists}

    # Collect all artist IDs from playlists (scrape with browser; API playlist items need user auth)
    all_ids = set()
    for pid in playlist_ids:
        print(f"Scraping playlist {pid}...")
        try:
            ids = get_playlist_artist_ids_with_browser(pid)
            all_ids |= ids
            print(f"  -> {len(ids)} unique artists in playlist. Total so far: {len(all_ids)}")
        except Exception as e:
            print(f"  -> Error: {e}. Skipped.")
        time.sleep(2.0)

    sp = create_client()

    missing_ids = [aid for aid in all_ids if aid not in existing_ids]
    print(f"\nArtists in playlists: {len(all_ids)}. Already in DB: {len(all_ids) - len(missing_ids)}. To add: {len(missing_ids)}.")

    if not missing_ids:
        print("Nothing new to add.")
        return

    added = []
    for i, aid in enumerate(missing_ids):
        if i > 0:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
        try:
            api_artist = fetch_artist(sp, aid)
        except SpotifyException as e:
            if e.http_status == 429:
                ra = int((e.headers or {}).get("Retry-After", 60))
                print(f"Rate limited. Wait {ra}s. Progress saved; re-run to resume.")
                break
            continue
        if not api_artist:
            continue
        record = api_artist_to_record(api_artist)
        artists.append(record)
        existing_ids.add(aid)
        added.append(record["name"])
        print(f"  Added: {record['name']} ({aid})")

    # Re-sort by streams (nulls last), re-assign popularity
    def sort_key(a):
        v = a.get("spotify_monthly_streams")
        return (-(v or 0), a.get("name", ""))

    artists.sort(key=sort_key)
    for rank, a in enumerate(artists, start=1):
        a["popularity"] = rank

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Added {len(added)} new artist(s). Total in file: {len(artists)}.")
    print("Next: run update_artists_spotify_streams.py to get monthly streams for new artists, then tidy_artists_json.py.")


if __name__ == "__main__":
    main()
