"""
Update followers (and optionally popularity) for all artists in artists_raw.json
using the Spotify API. Reads and overwrites the same file.

Spotify 2026 (Development Mode):
- Batch endpoint GET /artists?ids=... is REMOVED; use one request per artist (GET /artists/{id}).
- Rate limit: rolling 30-second window. We use a delay between requests to stay under the limit.
- If you get 429, the script respects Retry-After and saves progress; re-run to resume.
- In Dev Mode, Artist responses may omit followers/popularity (handled gracefully).
"""
import json
import os
import time

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials

# Path relative to this script: output/artists_raw.json (same repo layout as other scripts)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output")
INPUT_OUTPUT_FILE = "artists_raw.json"
# Stay under rolling 30s rate limit: ~1 request every 3s => ~10 requests per 30s
SLEEP_BETWEEN_REQUESTS = 3.0
SAVE_EVERY_N = 25  # Save progress to disk every N artists (resume-friendly)
MAX_RETRY_AFTER = 3600  # If 429 says wait > 1 hour, save and exit instead of sleeping

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
    """
    Fetch one artist by ID. Uses GET /artists/{id}.
    On 429 with long Retry-After, saves progress and exits so you can run again later.
    """
    for attempt in range(6):
        try:
            return sp.artist(artist_id)
        except SpotifyException as e:
            if e.http_status == 403:
                raise SystemExit(_403_MESSAGE) from e
            if e.http_status == 429:
                retry_after = 2
                try:
                    h = (e.headers or {})
                    retry_after = int(h.get("Retry-After", retry_after) or retry_after)
                except Exception:
                    pass
                if retry_after > MAX_RETRY_AFTER:
                    print(f"\nRate limited. Spotify says retry after {retry_after} s (~{retry_after // 3600} h).")
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


def _already_has_followers(artist: dict) -> bool:
    """True if this artist already has followers data (resume-friendly)."""
    fol = artist.get("followers")
    return isinstance(fol, dict) and "total" in fol


def main() -> None:
    path = os.path.join(OUTPUT_DIR, INPUT_OUTPUT_FILE)
    if not os.path.isdir(OUTPUT_DIR):
        raise SystemExit(f"Output directory not found: {OUTPUT_DIR}")
    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    if not artists:
        print("No artists in file. Exiting.")
        return

    sp = create_spotify_client()
    by_id = {a["id"]: a for a in artists}
    ids = list(by_id.keys())
    # Only fetch artists we haven't updated yet (resume after rate limit or interrupt)
    ids_to_fetch = [aid for aid in ids if not _already_has_followers(by_id[aid])]
    total = len(ids_to_fetch)
    if total == 0:
        print("All artists already have follower data. Nothing to do.")
        return
    if total < len(ids):
        print(f"Resuming: {len(ids) - total} already done, {total} remaining.")
    updated = 0

    for i, aid in enumerate(ids_to_fetch):
        raw = fetch_artist(sp, aid, path, ids, by_id)
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if raw and aid in by_id:
            obj = by_id[aid]
            # Dev Mode 2026 may omit followers/popularity; store what we get
            followers = raw.get("followers") or {}
            total_followers = followers.get("total")
            if total_followers is not None:
                try:
                    total_followers = int(total_followers)
                except (TypeError, ValueError):
                    total_followers = None
            obj["followers"] = {"total": total_followers}
            pop = raw.get("popularity")
            if pop is not None:
                obj["popularity"] = pop
            updated += 1

        if (i + 1) % SAVE_EVERY_N == 0 or (i + 1) == total:
            result = [by_id[aid] for aid in ids]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  Processed {i + 1}/{total} artists (saved)")

    result = [by_id[aid] for aid in ids]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Updated followers for {updated} artists. Saved to {path}")


if __name__ == "__main__":
    main()
