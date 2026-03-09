"""
Fetch Spotify artist image URL for each artist in artists_raw.json using the Spotify API.
Adds "image_url" (the first/largest image from the artist's "images" array).

Spotify 2026 (Development Mode):
- Batch GET /artists?ids=... is REMOVED; one request per artist (GET /artists/{id}).
- Rate limit: rolling 30-second window. We use a delay between requests.
- On 429, script respects Retry-After and saves progress; re-run to resume.

Usage:
  1. Set credentials (PowerShell):
       $env:SPOTIPY_CLIENT_ID="your_client_id"
       $env:SPOTIPY_CLIENT_SECRET="your_client_secret"
  2. Run:
       python scripts/update_artists_images.py
       python scripts/update_artists_images.py --start-after Joker   # Only artists after Joker
"""
import argparse
import json
import os
import time

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output")
INPUT_OUTPUT_FILE = "artists_raw.json"
SLEEP_BETWEEN_REQUESTS = 3.0
SAVE_EVERY_N = 25
MAX_RETRY_AFTER = 3600

_403_MESSAGE = """
Spotify returned 403 Forbidden. Check credentials and Dashboard settings.
See: https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide
"""


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing required environment variable: {name}\n"
            "Set Spotify credentials:\n"
            '  PowerShell: $env:SPOTIPY_CLIENT_ID="..."; $env:SPOTIPY_CLIENT_SECRET="..."'
        )
    return value


def create_spotify_client() -> spotipy.Spotify:
    require_env("SPOTIPY_CLIENT_ID")
    require_env("SPOTIPY_CLIENT_SECRET")
    auth_manager = SpotifyClientCredentials()
    return spotipy.Spotify(
        auth_manager=auth_manager,
        requests_timeout=20,
        retries=6,
        status_forcelist=(429, 500, 502, 503, 504),
        backoff_factor=0.4,
    )


def fetch_artist(sp: spotipy.Spotify, artist_id: str, path: str, ids: list, by_id: dict):
    """GET /artists/{id}. On 429 with long Retry-After, save and exit."""
    for attempt in range(6):
        try:
            return sp.artist(artist_id)
        except SpotifyException as e:
            if e.http_status == 403:
                raise SystemExit(_403_MESSAGE) from e
            if e.http_status == 429:
                retry_after = 2
                try:
                    h = e.headers or {}
                    retry_after = int(h.get("Retry-After", retry_after) or retry_after)
                except Exception:
                    pass
                if retry_after > MAX_RETRY_AFTER:
                    print(f"\nRate limited. Retry after {retry_after} s (~{retry_after // 3600} h).")
                    print("Progress saved. Run the script again later to resume.")
                    result = [by_id[aid] for aid in ids]
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    raise SystemExit(1) from e
                time.sleep(retry_after + 0.5)
                continue
            if e.http_status in (500, 502, 503, 504):
                time.sleep(min(8.0, 0.6 * (2**attempt)))
                continue
            raise
        except Exception:
            time.sleep(min(8.0, 0.6 * (2**attempt)))
    raise RuntimeError("Max retries exceeded")


def extract_image_url(artist_response: dict) -> str | None:
    """Get first image URL from Spotify artist 'images' array (largest first)."""
    images = artist_response.get("images") or []
    if not images:
        return None
    first = images[0]
    if isinstance(first, dict) and first.get("url"):
        return first["url"].strip() or None
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Spotify artist image_url for artists in artists_raw.json.")
    parser.add_argument("--start-after", metavar="NAME", help="Only process artists that appear after this artist (e.g. Joker).")
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
        name = (args.start_after or "").strip()
        found = None
        for i, a in enumerate(artists):
            if (a.get("name") or "").strip() == name:
                found = i
        if found is None:
            raise SystemExit(f"Artist '{name}' not found in JSON.")
        start_index = found + 1
        print(f"Processing only artists after '{name}' (from index {start_index + 1} to end).\n")

    sp = create_spotify_client()
    by_id = {a["id"]: a for a in artists}
    ids = list(by_id.keys())
    aids_after = {artists[i]["id"] for i in range(start_index, len(artists))} if start_index > 0 else set(ids)
    ids_to_fetch = [aid for aid in ids if aid in aids_after and not by_id[aid].get("image_url")]
    total = len(ids_to_fetch)
    if total == 0:
        print("All artists already have image_url set. Nothing to do.")
        return
    if total < len(ids):
        print(f"Resuming: {len(ids) - total} already have image_url, {total} remaining.")

    updated = 0
    for i, aid in enumerate(ids_to_fetch):
        raw = fetch_artist(sp, aid, path, ids, by_id)
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if raw and aid in by_id:
            url = extract_image_url(raw)
            by_id[aid]["image_url"] = url
            if url:
                updated += 1

        if (i + 1) % SAVE_EVERY_N == 0 or (i + 1) == total:
            result = [by_id[aid] for aid in ids]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  Processed {i + 1}/{total} (saved), with image: {updated}")

    result = [by_id[aid] for aid in ids]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Done. image_url set for {updated}/{total} artists. Saved to {path}")


if __name__ == "__main__":
    main()
