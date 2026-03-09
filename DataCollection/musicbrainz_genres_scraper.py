"""
Fetch genre/tag data from MusicBrainz for artists in artists_raw.json and update the file.
Uses the same search + best-match logic as musicbrainz_scraper.py, then fetches tags/genres by artist MBID.
"""
import musicbrainzngs
import json
import time
import os
import sys

# Add parent so we can import from musicbrainz_scraper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from musicbrainz_scraper import search_artist_musicbrainz, get_best_match

# Set up the MusicBrainz client (same as main scraper)
musicbrainzngs.set_useragent(
    "TurkishArtistDataCollector",
    "1.0",
    "https://github.com/example/turkish-artists"
)


def get_artist_by_id_with_tags(mbid):
    """
    Fetch full artist from MusicBrainz including tags and genres.
    """
    try:
        result = musicbrainzngs.get_artist_by_id(mbid, includes=["tags"])
        return result.get("artist")
    except Exception as e:
        print(f"  get_artist error: {type(e).__name__}")
        return None


def extract_genres_from_artist(artist_data):
    """
    Extract genre/tag names from MusicBrainz artist data.
    Prefers official genres, then community tags (sorted by count if available).
    Returns a list of unique genre strings.
    """
    genres = []
    seen = set()

    def add(name):
        if not name or not isinstance(name, str):
            return
        n = name.strip()
        if n and n.lower() not in seen:
            seen.add(n.lower())
            genres.append(n)

    if not artist_data:
        return genres

    # Official MusicBrainz genres (if available)
    for key in ("genre-list", "genre_list"):
        lst = artist_data.get(key)
        if isinstance(lst, list):
            for item in lst:
                if isinstance(item, dict) and "name" in item:
                    add(item["name"])
                elif isinstance(item, str):
                    add(item)
        elif isinstance(lst, dict):
            for name in lst.values() if isinstance(lst, dict) else []:
                add(name)

    # Community tags (often used as genres)
    for key in ("tag-list", "tag_list"):
        lst = artist_data.get(key)
        if isinstance(lst, list):
            # Sort by count descending if present
            with_count = [(item.get("name") or item, int(item.get("count", 0))) for item in lst if isinstance(item, dict) and item.get("name")]
            without_count = [item for item in lst if isinstance(item, str)]
            with_count.sort(key=lambda x: -x[1])
            for name, _ in with_count:
                add(name)
            for name in without_count:
                add(name)

    return genres


def update_artists_genres(input_file, output_file=None, start_from=0, only_empty=True, refresh_all=False, start_after_name=None):
    """
    Read artists from JSON, fetch MusicBrainz genres/tags for each, update the file.
    If only_empty=True (default), only fetch for artists with empty genres.
    If refresh_all=True, refetch for all artists (overwrites existing genres).
    If start_after_name is set (e.g. "Joker"), only process artists that appear after that name in the list.
    """
    if output_file is None:
        output_file = input_file

    with open(input_file, "r", encoding="utf-8") as f:
        artists = json.load(f)

    min_index = 0
    if start_after_name:
        found = None
        for i, a in enumerate(artists):
            if (a.get("name") or "").strip() == start_after_name.strip():
                found = i
        if found is None:
            raise SystemExit(f"Artist '{start_after_name}' not found in JSON.")
        min_index = found + 1
        print(f"Processing only artists after '{start_after_name}' (from index {min_index + 1} to end).\n")

    total = len(artists)
    updated_count = 0
    not_found_count = 0
    skipped_count = 0

    if only_empty and not refresh_all:
        print("Mode: Only fetching genres for artists with empty genres.")
    else:
        print("Mode: Fetching genres for all artists (refresh_all).")

    if start_from > 0:
        print(f"Resuming from artist index {start_from + 1}...")
    elif min_index > 0:
        print(f"Starting genre fetch for artists {min_index + 1} to {total}...")
    else:
        print(f"Starting genre fetch for {total} artists...")
    print("Rate limited to 1 request per second (MusicBrainz API).\n")

    for i, artist in enumerate(artists):
        if i < min_index:
            continue
        if i < start_from:
            continue

        if only_empty and not refresh_all and artist.get("genres"):
            skipped_count += 1
            continue

        name = artist.get("name", "")
        try:
            display_name = name.encode("cp1254", errors="replace").decode("cp1254")
        except Exception:
            display_name = name.encode("ascii", errors="replace").decode("ascii")
        print(f"[{i+1}/{total}] {display_name}...", end=" ", flush=True)

        search_results = search_artist_musicbrainz(name)
        time.sleep(1.1)

        if not search_results:
            not_found_count += 1
            print("Not found")
            continue

        best_match = get_best_match(search_results, name)
        if not best_match:
            not_found_count += 1
            print("No good match")
            continue

        mbid = best_match.get("id")
        if not mbid:
            not_found_count += 1
            print("No MBID")
            continue

        full_artist = get_artist_by_id_with_tags(mbid)
        time.sleep(1.1)

        if not full_artist:
            not_found_count += 1
            print("No detail")
            continue

        genre_list = extract_genres_from_artist(full_artist)
        artist["genres"] = genre_list
        updated_count += 1
        print(f"OK ({len(genre_list)} genres)" if genre_list else "OK (no genres)")

        if (i + 1) % 50 == 0:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(artists, f, indent=2, ensure_ascii=False)
            print(f"\n--- Progress saved ({i+1}/{total}) ---\n")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(artists, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"Total artists: {total}")
    print(f"Skipped (already have genres): {skipped_count}")
    print(f"Updated: {updated_count}")
    print(f"Not found: {not_found_count}")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
MusicBrainz Genres Scraper
==========================

Fetches genre/tag data from MusicBrainz for artists in artists_raw.json and updates the file.

Usage:
  python musicbrainz_genres_scraper.py                  # Only artists with empty genres
  python musicbrainz_genres_scraper.py --all            # All artists (refresh genres)
  python musicbrainz_genres_scraper.py --continue=N     # Resume from index N (0-based)
  python musicbrainz_genres_scraper.py --start-after Joker   # Only artists below Joker
  python musicbrainz_genres_scraper.py --test           # Test with first 5 artists (no save)
  python musicbrainz_genres_scraper.py --help           # This help

Examples:
  python musicbrainz_genres_scraper.py --all
  python musicbrainz_genres_scraper.py --continue=100
  python musicbrainz_genres_scraper.py --start-after Joker
        """)
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Testing genre fetch with first 5 artists (dry run)...\n")
        input_file = os.path.join(os.path.dirname(__file__), "output", "artists_raw.json")
        with open(input_file, "r", encoding="utf-8") as f:
            artists = json.load(f)
        for artist in artists[:5]:
            name = artist.get("name", "")
            print(f"Searching: {name}")
            search_results = search_artist_musicbrainz(name)
            time.sleep(1.1)
            if not search_results:
                print("  Not found\n")
                continue
            best = get_best_match(search_results, name)
            if not best or not best.get("id"):
                print("  No match/MBID\n")
                continue
            full = get_artist_by_id_with_tags(best["id"])
            time.sleep(1.1)
            genres = extract_genres_from_artist(full) if full else []
            print(f"  Genres: {genres}\n")
        print("Test done. Run without --test to update the file.")
    else:
        input_file = os.path.join(os.path.dirname(__file__), "output", "artists_raw.json")
        start_from = 0
        only_empty = True
        start_after_name = None
        args_list = sys.argv[1:]
        idx = 0
        while idx < len(args_list):
            arg = args_list[idx]
            if arg.startswith("--continue="):
                start_from = int(arg.split("=")[1])
            elif arg == "--all":
                only_empty = False
            elif arg.startswith("--start-after="):
                start_after_name = arg.split("=", 1)[1].strip()
            elif arg == "--start-after" and idx + 1 < len(args_list) and not args_list[idx + 1].startswith("--"):
                start_after_name = args_list[idx + 1].strip()
                idx += 1
            idx += 1
        update_artists_genres(input_file, start_from=start_from, only_empty=only_empty, start_after_name=start_after_name)
