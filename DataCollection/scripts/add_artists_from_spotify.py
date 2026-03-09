"""
Add specific Turkish artists to artists_raw.json by name (no duplicates).

Use this when you know an artist name (e.g. "Erol Evgin") that should be in the
database but isn't—e.g. big artists with 1M+ streams who don't appear in current
chart playlists. For discovering missing artists from charts, use
discover_artists_from_playlists.py instead.

Searches Spotify by name; if the artist ID is not already in our JSON, adds them.
New artists get spotify_monthly_streams, top_track_* as null; run
update_artists_spotify_streams.py and update_artists_preview.py afterward.

Usage:
  1. Set credentials: $env:SPOTIPY_CLIENT_ID="..."; $env:SPOTIPY_CLIENT_SECRET="..."
  2. By name:  python scripts/add_artists_from_spotify.py "Erol Evgin" "Another Artist"
  3. From file: python scripts/add_artists_from_spotify.py --file artists_to_add.txt
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
ARTISTS_FILE = "artists_raw.json"
SLEEP_BETWEEN_REQUESTS = 2.0
DEFAULT_NATIONALITY = "Turkey"


def require_env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise SystemExit(
            f"Missing {name}. Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET."
        )
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


def search_artist(sp: spotipy.Spotify, name: str) -> dict | None:
    """Search for an artist by name; return first result or None."""
    try:
        r = sp.search(q=name.strip(), type="artist", limit=5)
    except SpotifyException as e:
        if e.http_status == 429:
            raise
        return None
    items = (r.get("artists") or {}).get("items") or []
    if not items:
        return None
    return items[0]


def artist_response_to_record(api_artist: dict) -> dict:
    """Convert Spotify API artist object to our JSON schema."""
    images = api_artist.get("images") or []
    image_url = images[0]["url"] if images and images[0].get("url") else None
    return {
        "id": api_artist["id"],
        "name": api_artist["name"],
        "gender": None,
        "genres": api_artist.get("genres") or [],
        "popularity": 0,  # Will be re-assigned when you re-run tidy/sort
        "debut": None,
        "nationality": DEFAULT_NATIONALITY,
        "group_size": 1,
        "spotify_monthly_streams": None,
        "image_url": image_url,
        "top_track_name": None,
        "top_track_uri": None,
        "top_track_id": None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Add artists from Spotify to artists_raw.json (no duplicates)."
    )
    parser.add_argument(
        "names",
        nargs="*",
        help="Artist names to search and add",
    )
    parser.add_argument(
        "--file",
        "-f",
        metavar="PATH",
        help="Text file with one artist name per line",
    )
    args = parser.parse_args()

    names = list(args.names) if args.names else []
    if args.file:
        path = os.path.abspath(args.file)
        if not os.path.isfile(path):
            raise SystemExit(f"File not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                n = line.strip()
                if n and n not in names:
                    names.append(n)

    if not names:
        raise SystemExit(
            "Give artist names: python add_artists_from_spotify.py \"Erol Evgin\"\n"
            "Or use --file path/to/names.txt"
        )

    path = os.path.join(OUTPUT_DIR, ARTISTS_FILE)
    if not os.path.isfile(path):
        raise SystemExit(f"Not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    existing_ids = {a["id"] for a in artists}
    sp = create_client()
    added = []
    skipped_dup = []
    not_found = []

    for i, name in enumerate(names):
        if i > 0:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
        try:
            api_artist = search_artist(sp, name)
        except SpotifyException as e:
            if e.http_status == 429:
                ra = int((e.headers or {}).get("Retry-After", 60))
                print(f"Rate limited. Wait {ra}s or re-run later.")
                raise SystemExit(1) from e
            not_found.append(name)
            continue

        if not api_artist:
            not_found.append(name)
            continue

        aid = api_artist["id"]
        if aid in existing_ids:
            skipped_dup.append((name, api_artist["name"], aid))
            continue

        record = artist_response_to_record(api_artist)
        artists.append(record)
        existing_ids.add(aid)
        added.append((name, record["name"], record["id"]))
        print(f"  Added: {record['name']} (id: {aid})")

    # Re-sort by spotify_monthly_streams desc, nulls last; re-assign popularity
    def sort_key(a):
        v = a.get("spotify_monthly_streams")
        return (-(v or 0), a.get("name", ""))

    artists.sort(key=sort_key)
    for rank, a in enumerate(artists, start=1):
        a["popularity"] = rank

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Added {len(added)} new artist(s).")
    if skipped_dup:
        print(f"Skipped (already in DB): {len(skipped_dup)}")
        for q, resolved, aid in skipped_dup:
            print(f"  - '{q}' -> {resolved} ({aid})")
    if not_found:
        print(f"Not found on Spotify: {len(not_found)}")
        for n in not_found:
            print(f"  - {n}")
    print(f"Total artists in file: {len(artists)}. Run update_artists_spotify_streams.py and update_artists_preview.py for new rows.")


if __name__ == "__main__":
    main()
