"""
Fetch YouTube channel subscriber counts for artists in artists_raw.json and add
youtube_subscribers and youtube_views to the same file. One run for all artists
if you use multiple API keys (see below).

Uses YouTube Data API v3 (no Spotify needed).
Setup: https://developers.google.com/youtube/v3/getting-started
  - One project = one API key = 10,000 units/day. One artist ≈ 101 units → ~99 artists per key per day.

ONE KEY PER RUN (simplest):
  Run: python update_artists_youtube.py --key "YOUR_API_KEY"
  Each run does up to 99 artists (one key's quota). Next run: create a new key, then
  python update_artists_youtube.py --key "NEW_KEY"  → resumes and does the next 99. Repeat until done.

MULTIPLE KEYS IN ONE RUN:
  Set: $env:YOUTUBE_API_KEYS="key1,key2,key3,key4,key5,key6"
  Run once with no --key; script rotates keys and does all artists in one go.
"""
import json
import os
import time
import urllib.parse
import urllib.request

INPUT_OUTPUT_FILE = "artists_raw.json"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
SLEEP_BETWEEN_REQUESTS = 0.2
SAVE_EVERY_N = 25
# 10k quota per key; 101 units per artist → 99 artists per key
ARTISTS_PER_KEY = 99


def get_api_keys() -> list[str]:
    """Return list of API keys from YOUTUBE_API_KEYS (comma-separated) or single YOUTUBE_API_KEY."""
    multi = os.getenv("YOUTUBE_API_KEYS", "").strip()
    if multi:
        keys = [k.strip() for k in multi.split(",") if k.strip()]
        if keys:
            return keys
    single = os.getenv("YOUTUBE_API_KEY", "").strip()
    if single:
        return [single]
    raise SystemExit(
        "Missing YouTube API key(s).\n"
        "One run for all artists: create 5–6 projects in Google Cloud (each: enable YouTube Data API v3, create API key).\n"
        'Set: $env:YOUTUBE_API_KEYS="key1,key2,key3,key4,key5,key6"\n'
        "Or single key: $env:YOUTUBE_API_KEY=\"your_key\" (then only ~99 artists per day)."
    )


def youtube_search(api_key: str, q: str) -> list:
    """Search for channels; returns list of channel IDs (max 5). Cost: 100 units."""
    params = {
        "part": "snippet",
        "q": q,
        "type": "channel",
        "maxResults": 5,
        "key": api_key,
    }
    url = YOUTUBE_API_BASE + "/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []
    items = (data or {}).get("items", []) or []
    return [it["id"]["channelId"] for it in items if (it.get("id") or {}).get("channelId")]


def youtube_channels(api_key: str, channel_ids: list) -> list:
    """Get channel statistics. Cost: 1 unit. channel_ids can be up to 50."""
    if not channel_ids:
        return []
    params = {
        "part": "statistics",
        "id": ",".join(channel_ids[:50]),
        "key": api_key,
    }
    url = YOUTUBE_API_BASE + "/channels?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []
    return (data or {}).get("items", []) or []


def get_best_channel_stats(api_key: str, artist_name: str) -> dict | None:
    """
    Search for artist name, take first channel, return {subscriber_count, view_count} or None.
    Uses 100 (search) + 1 (channels) = 101 quota units.
    """
    channel_ids = youtube_search(api_key, artist_name + " topic")
    if not channel_ids:
        channel_ids = youtube_search(api_key, artist_name)
    if not channel_ids:
        return None
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    channels = youtube_channels(api_key, [channel_ids[0]])
    if not channels:
        return None
    stats = (channels[0] or {}).get("statistics") or {}
    try:
        subs = int(stats.get("subscriberCount") or 0)
        views = int(stats.get("viewCount") or 0)
        return {"subscriber_count": subs, "view_count": views}
    except (TypeError, ValueError):
        return None


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Add YouTube subscriber (and view) counts to artists_raw.json")
    parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="YouTube API key for this run (does ~99 artists; run again with a new key to resume)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Max artists this run (default: 99 when using --key, else all if YOUTUBE_API_KEYS has 5–6 keys)",
    )
    args = parser.parse_args()

    if args.key and args.key.strip():
        api_keys = [args.key.strip()]
    else:
        api_keys = get_api_keys()
    path = os.path.join(os.path.dirname(__file__), INPUT_OUTPUT_FILE)

    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    if not artists:
        print("No artists in file. Exiting.")
        return

    indices_to_fetch = [
        i for i, a in enumerate(artists)
        if a.get("youtube_subscribers") is None
    ]
    total_remaining = len(indices_to_fetch)
    if total_remaining == 0:
        print("All artists already have YouTube data. Nothing to do.")
        return

    max_allowed = len(api_keys) * ARTISTS_PER_KEY
    if args.max is not None:
        to_do = indices_to_fetch[: args.max]
    else:
        to_do = indices_to_fetch[: max_allowed]
        if len(api_keys) == 1 and total_remaining > ARTISTS_PER_KEY:
            print(f"Single API key: processing first {len(to_do)} artists (use 5–6 keys in YOUTUBE_API_KEYS for one run of all).")

    n_this_run = len(to_do)
    if args.key and args.key.strip():
        print(f"Using --key for this run; up to {n_this_run} artists (then run again with a new --key to resume).")
    elif n_this_run < total_remaining:
        print(f"Resuming: {total_remaining - n_this_run} already done, {n_this_run} this run.")
    elif len(api_keys) > 1:
        print(f"Using {len(api_keys)} API keys → one run for all {n_this_run} artists.")

    updated = 0
    for k, idx in enumerate(to_do):
        artist = artists[idx]
        name = (artist.get("name") or "").strip()
        # Rotate key every ARTISTS_PER_KEY artists so each key stays under quota
        api_key = api_keys[(k // ARTISTS_PER_KEY) % len(api_keys)]
        if not name:
            artist["youtube_subscribers"] = None
            artist["youtube_views"] = None
            continue
        result = get_best_channel_stats(api_key, name)
        if result:
            artist["youtube_subscribers"] = result["subscriber_count"]
            artist["youtube_views"] = result["view_count"]
            updated += 1
        else:
            artist["youtube_subscribers"] = None
            artist["youtube_views"] = None

        if (k + 1) % SAVE_EVERY_N == 0 or (k + 1) == n_this_run:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(artists, f, ensure_ascii=False, indent=2)
            print(f"  Processed {k + 1}/{n_this_run} artists (saved)")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)
    print(f"Done. Updated {updated}/{n_this_run} artists with YouTube data. Saved to {INPUT_OUTPUT_FILE}")
    if total_remaining > n_this_run:
        print(f"Run again to continue ({(total_remaining - n_this_run)} artists left).")


if __name__ == "__main__":
    main()
