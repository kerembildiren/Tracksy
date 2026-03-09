"""
Sort the artists below Joker by spotify_monthly_streams (highest first), place them
right under Joker, then remove any with monthly streams < 200k. Everyone above Joker
is left unchanged. Prints the list of deleted artists.
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(SCRIPT_DIR, "..", "output", "artists_raw.json")
MIN_STREAMS = 200_000


def main():
    with open(PATH, "r", encoding="utf-8") as f:
        artists = json.load(f)

    # Find Joker (last occurrence if multiple)
    joker_index = None
    for i, a in enumerate(artists):
        if (a.get("name") or "").strip() == "Joker":
            joker_index = i
    if joker_index is None:
        raise SystemExit("Artist 'Joker' not found in JSON.")

    head = artists[0 : joker_index + 1]   # through Joker, untouched
    tail = artists[joker_index + 1 :]      # everyone below Joker

    # Sort tail by spotify_monthly_streams descending (nulls last)
    def sort_key(a):
        v = a.get("spotify_monthly_streams")
        return (-(v or 0), a.get("name", ""))

    tail_sorted = sorted(tail, key=sort_key)

    # Keep only those with streams >= 200k (drop the rest)
    kept_tail = []
    removed = []
    for a in tail_sorted:
        streams = a.get("spotify_monthly_streams")
        if streams is not None and streams < MIN_STREAMS:
            removed.append(a)
        else:
            kept_tail.append(a)

    artists_new = head + kept_tail

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(artists_new, f, ensure_ascii=False, indent=2)

    print(f"Artists below Joker: {len(tail)} -> kept {len(kept_tail)}, removed {len(removed)} (streams < {MIN_STREAMS:,}).")
    print(f"Total artists in file: {len(artists_new)} (unchanged above Joker: {len(head)}).")
    if removed:
        print("\nDeleted artists (below Joker, streams < 200k):")
        for a in removed:
            streams = a.get("spotify_monthly_streams") or 0
            print(f"  - {a.get('name')} (id: {a.get('id')}, streams: {streams:,})")
    else:
        print("\nNo artists were deleted.")


if __name__ == "__main__":
    main()
