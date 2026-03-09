"""
Tidy artists_raw.json:
1. Remove keys: followers, lastfm_listeners, lastfm_playcount, spotify_monthly_listeners
2. Sort by spotify_monthly_streams descending (highest first; nulls last)
3. Assign popularity = rank (1 = most streams, N = least streams)
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(SCRIPT_DIR, "..", "output", "artists_raw.json")

KEYS_TO_REMOVE = {"followers", "lastfm_listeners", "lastfm_playcount", "spotify_monthly_listeners"}


def main():
    with open(PATH, "r", encoding="utf-8") as f:
        artists = json.load(f)

    # 1. Remove unwanted keys from each artist
    for a in artists:
        for key in KEYS_TO_REMOVE:
            a.pop(key, None)

    # 2. Sort by spotify_monthly_streams descending (nulls last)
    def sort_key(a):
        v = a.get("spotify_monthly_streams")
        return (-(v or 0), a.get("name", ""))

    artists.sort(key=sort_key)

    # 3. Assign popularity = rank (1-based)
    for rank, artist in enumerate(artists, start=1):
        artist["popularity"] = rank

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)

    print(f"Done. Removed {KEYS_TO_REMOVE}. Sorted by spotify_monthly_streams. Assigned popularity 1..{len(artists)}.")
    print(f"Top 3: {[(a['name'], a['spotify_monthly_streams'], a['popularity']) for a in artists[:3]]}")
    print(f"Bottom 3: {[(a['name'], a['spotify_monthly_streams'], a['popularity']) for a in artists[-3:]]}")


if __name__ == "__main__":
    main()
