"""
Fetch a representative track for each artist and store in artists_raw.json.
Uses only Spotify Search API (one request per artist). Search by artist name,
take first track by that artist. Stores top_track_id (for embed player),
top_track_name, top_track_uri. Preview URLs are no longer returned by the API;
the game uses Spotify's embed widget to play the track instead.

Rate limit: one search per artist, 3s delay. On 429, respects Retry-After and saves; re-run to resume.
Resume: skips artists that already have top_track_id set.

Usage:
  python scripts/update_artists_preview.py
  python scripts/update_artists_preview.py --start-after Joker   # Only artists after Joker
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
MARKET = "TR"
SLEEP_BETWEEN_REQUESTS = 3.0
SAVE_EVERY_N = 20
MAX_RETRY_AFTER = 3600


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


def get_top_track_from_search(sp: spotipy.Spotify, artist_id: str, artist_name: str) -> tuple[str | None, str | None, str | None]:
    """Search tracks by artist name; return (track_id, track_name, spotify_url) for first track by this artist."""
    if not (artist_name or "").strip():
        return None, None, None
    result = sp.search(q=artist_name, type="track", limit=10, market=MARKET)
    tracks = (result.get("tracks") or {}).get("items") or []
    # First track where this artist is in the artists list (id or name match)
    for t in tracks:
        if not t:
            continue
        tid = t.get("id")
        if not tid:
            continue
        for a in t.get("artists") or []:
            if (a or {}).get("id") == artist_id or (a or {}).get("name", "").lower() == (artist_name or "").lower():
                name = t.get("name") or ""
                ext = t.get("external_urls") or {}
                return tid, name, ext.get("spotify") or ""
    # Fallback: first track in results (e.g. featuring this artist)
    for t in tracks:
        tid = t.get("id")
        if tid:
            name = t.get("name") or ""
            ext = t.get("external_urls") or {}
            return tid, name, ext.get("spotify") or ""
    return None, None, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch top track (id, name, uri) for artists in artists_raw.json.")
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
    ids_to_fetch = [aid for aid in ids if aid in aids_after and not by_id[aid].get("top_track_id")]
    total = len(ids_to_fetch)
    if total == 0:
        print("All artists already have top_track_id set. Nothing to do.")
        return

    print(f"Fetching top track for {total} artists (rate limit safe).")

    updated = 0
    for i, aid in enumerate(ids_to_fetch):
        artist_name = by_id[aid].get("name") or ""
        track_id, track_name, spotify_url = None, None, None
        for attempt in range(6):
            try:
                track_id, track_name, spotify_url = get_top_track_from_search(sp, aid, artist_name)
                break
            except SpotifyException as e:
                if e.http_status == 429:
                    retry_after = 2
                    try:
                        h = e.headers or {}
                        retry_after = int(h.get("Retry-After", retry_after) or retry_after)
                    except Exception:
                        pass
                    if retry_after > MAX_RETRY_AFTER:
                        result = [by_id[aid] for aid in ids]
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                        print("Rate limited. Progress saved. Run again later to resume.")
                        raise SystemExit(1) from e
                    time.sleep(retry_after + 0.5)
                    continue
                if e.http_status in (500, 502, 503, 504):
                    time.sleep(min(8.0, 0.6 * (2**attempt)))
                    continue
                raise
            except Exception:
                time.sleep(min(8.0, 0.6 * (2**attempt)))

        by_id[aid]["top_track_id"] = track_id
        by_id[aid]["top_track_name"] = track_name if track_name else None
        by_id[aid]["top_track_uri"] = spotify_url if spotify_url else None
        if track_id:
            updated += 1

        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if (i + 1) % SAVE_EVERY_N == 0 or (i + 1) == total:
            result = [by_id[aid] for aid in ids]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  Processed {i + 1}/{total} (saved), with track: {updated}")

    result = [by_id[aid] for aid in ids]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Done. top_track_id set for {updated}/{total} artists. Saved to {path}")


if __name__ == "__main__":
    main()
