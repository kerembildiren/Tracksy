"""
Remove artists with spotify_monthly_streams < 200,000 from artists_raw.json.
Re-sorts by streams (desc) and re-assigns popularity rank.
Prints the list of deleted artists.
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(SCRIPT_DIR, "..", "output", "artists_raw.json")
MIN_STREAMS = 200_000


def main():
    with open(PATH, "r", encoding="utf-8") as f:
        artists = json.load(f)

    kept = []
    removed = []
    for a in artists:
        streams = a.get("spotify_monthly_streams")
        if streams is not None and streams < MIN_STREAMS:
            removed.append(a)
        else:
            kept.append(a)

    # Sort kept by spotify_monthly_streams descending (nulls last)
    def sort_key(a):
        v = a.get("spotify_monthly_streams")
        return (-(v or 0), a.get("name", ""))

    kept.sort(key=sort_key)

    # Re-assign popularity (1-based rank)
    for rank, artist in enumerate(kept, start=1):
        artist["popularity"] = rank

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    print(f"Removed {len(removed)} artist(s) with < {MIN_STREAMS:,} monthly streams.")
    print(f"Kept {len(kept)} artists. Re-assigned popularity 1..{len(kept)}.")
    if removed:
        print("\nDeleted artists:")
        for a in removed:
            streams = a.get("spotify_monthly_streams") or 0
            print(f"  - {a.get('name')} (id: {a.get('id')}, streams: {streams:,})")
    else:
        print("\nNo artists were deleted.")


if __name__ == "__main__":
    main()
