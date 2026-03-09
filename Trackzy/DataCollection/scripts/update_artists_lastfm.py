"""
Fetch Last.fm popularity data (listeners + playcount) for artists in artists_raw.json
and add it to the same file. Uses artist name only — no Spotify API needed.

Get a free API key: https://www.last.fm/api/account/create
Set: $env:LASTFM_API_KEY="your_api_key"
"""
import json
import os
import time
import urllib.parse
import urllib.request

INPUT_OUTPUT_FILE = "artists_raw.json"
LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"
SLEEP_BETWEEN_REQUESTS = 1.0  # Last.fm rate limit: stay under ~5/sec, 1/sec is safe
SAVE_EVERY_N = 50


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing environment variable: {name}\n"
            "Get a free API key at https://www.last.fm/api/account/create\n"
            'Then set: $env:LASTFM_API_KEY="your_api_key"'
        )
    return value


def fetch_artist_lastfm(api_key: str, artist_name: str) -> dict | None:
    """Call Last.fm artist.getInfo. Returns stats dict with listeners & playcount or None. Raises on error 29."""
    params = {
        "method": "artist.getInfo",
        "artist": artist_name,
        "api_key": api_key,
        "format": "json",
        "autocorrect": "1",
    }
    url = LASTFM_API_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ArtistPopularityScript/1.0 (Python)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    if (data or {}).get("error") == 29:
        raise RuntimeError("LASTFM_RATE_LIMIT")
    artist = (data or {}).get("artist")
    if not artist:
        return None
    stats = (artist or {}).get("stats") or {}
    listeners = stats.get("listeners")
    playcount = stats.get("playcount")
    if listeners is None and playcount is None:
        return None
    return {
        "listeners": int(listeners) if listeners is not None else None,
        "playcount": int(playcount) if playcount is not None else None,
    }


def main() -> None:
    api_key = require_env("LASTFM_API_KEY")
    path = os.path.join(os.path.dirname(__file__), INPUT_OUTPUT_FILE)

    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    if not artists:
        print("No artists in file. Exiting.")
        return

    # Only process artists that don't have Last.fm data yet (resume support)
    to_fetch = [i for i, a in enumerate(artists) if a.get("lastfm_listeners") is None and a.get("lastfm_playcount") is None]
    total = len(to_fetch)
    if total == 0:
        print("All artists already have Last.fm data. Nothing to do.")
        return
    if total < len(artists):
        print(f"Resuming: {len(artists) - total} already done, {total} remaining.")

    updated = 0
    for k, idx in enumerate(to_fetch):
        artist = artists[idx]
        name = (artist.get("name") or "").strip()
        if not name:
            continue
        try:
            stats = fetch_artist_lastfm(api_key, name)
        except RuntimeError as e:
            if "LASTFM_RATE_LIMIT" in str(e):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(artists, f, ensure_ascii=False, indent=2)
                raise SystemExit("Last.fm rate limit (error 29). Progress saved. Wait a few minutes and run again.") from e
            raise
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if stats is not None:
            artist["lastfm_listeners"] = stats.get("listeners")
            artist["lastfm_playcount"] = stats.get("playcount")
            updated += 1
        else:
            artist["lastfm_listeners"] = None
            artist["lastfm_playcount"] = None

        if (k + 1) % SAVE_EVERY_N == 0 or (k + 1) == total:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(artists, f, ensure_ascii=False, indent=2)
            print(f"  Processed {k + 1}/{total} artists (saved)")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)
    print(f"Done. Updated {updated}/{total} artists with Last.fm data. Saved to {INPUT_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
