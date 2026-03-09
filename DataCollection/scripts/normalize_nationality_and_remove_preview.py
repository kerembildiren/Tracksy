"""
Normalize artists_raw.json:
1. Set nationality to "Turkey" for every artist.
2. Remove the preview_url key from every artist (older entries don't have it).
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Resolve to absolute path so we always update the same file regardless of cwd
PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "output", "artists_raw.json"))


def main():
    with open(PATH, "r", encoding="utf-8") as f:
        artists = json.load(f)

    nationality_changed = 0
    for artist in artists:
        if artist.get("nationality") != "Turkey":
            artist["nationality"] = "Turkey"
            nationality_changed += 1
        artist.pop("preview_url", None)

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)

    print(f"Set nationality to Turkey for {nationality_changed} artist(s).")
    print("Removed preview_url from all artists.")
    print(f"Saved: {PATH}")


if __name__ == "__main__":
    main()
