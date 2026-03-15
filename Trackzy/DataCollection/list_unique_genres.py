"""
List all unique genres from artists_raw.json.
Output: printed to stdout and optionally written to output/unique_genres.txt.
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "output", "artists_raw.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "output", "unique_genres.txt")

def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        artists = json.load(f)
    genres = set()
    for a in artists:
        for g in (a.get("genres") or []):
            if g and str(g).strip():
                genres.add(str(g).strip())
    sorted_genres = sorted(genres)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted_genres))
    print(f"Unique genres ({len(sorted_genres)}):")
    for g in sorted_genres:
        print(f"  {g}")
    print(f"\nAlso written to: {OUT_PATH}")

if __name__ == "__main__":
    main()
