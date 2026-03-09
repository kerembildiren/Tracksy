"""
Assign a single genre to artists below Joker using only the canonical genres
that appear in artists before (and including) Joker. If an artist has no genre,
only "turkish", or no mappable tag, set genres to [] (null).
"""
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(SCRIPT_DIR, "..", "output", "artists_raw.json")

# Tags that are not useful for genre (skip; if only these remain -> null)
SKIP_TAGS = {
    "turkish", "american", "german", "english", "cypriot", "uk", "usa",
    "2008 universal fire victim", "producer", "author", "singer-songwriter",
    "italian orchestra",
}

# Map lowercase MusicBrainz-style tag (or substring) -> canonical genre name.
# Canonical set is taken from artists before Joker; we map to exact strings they use.
TAG_TO_CANONICAL = {}

def _add(tag, canonical):
    TAG_TO_CANONICAL[tag.lower().strip()] = canonical

# Arabesk / Fantezi (canonical: Arabesk)
_add("arabesk", "Arabesk")
_add("fantezi", "Arabesk")

# Pop
_add("pop", "Pop")
_add("turkish pop", "Pop")
_add("turkish pop music", "Pop")
_add("dance-pop", "Pop")
_add("traditional pop", "Pop")
_add("jangle pop", "Pop")
_add("chamber pop", "Pop")
_add("power pop", "Pop")

# Rock
_add("rock", "Rock")
_add("alternative rock", "Rock")
_add("pop rock", "Rock")
_add("folk rock", "Rock")
_add("anatolian rock", "Rock")
_add("acoustic rock", "Rock")
_add("electronic rock", "Rock")
_add("glam rock", "Rock")
_add("grunge", "Rock")
_add("college rock", "Rock")
_add("neo-psychedelia", "Rock")
_add("experimental", "Rock")

# Folk
_add("folk", "Folk")
_add("turkish folk", "Folk")
_add("turkish folk music", "Folk")
_add("contemporary folk", "Folk")
_add("uzun hava", "Folk")

# Classical
_add("classical", "Classical")
_add("turkish classical", "Classical")
_add("chamber orchestra", "Classical")
_add("orchestra", "Classical")

# Jazz
_add("jazz", "Jazz")
_add("vocal jazz", "Jazz")

# Electronic
_add("electronic", "Electronic")
_add("elektronik", "Elektronik")
_add("dance", "Electronic")

# Indie
_add("indie", "Indie")
_add("indie rock", "Rock")
_add("indie pop", "Pop")

# Punk
_add("punk", "Punk")
_add("pop punk", "Punk")

# Rap
_add("rap", "Rap")
_add("hip hop", "Rap")
_add("turkish rap", "Rap")
_add("turkish hip hop", "Rap")

# Alternative
_add("alternative", "Alternative")
_add("alternative country", "Alternative")

# Chanson / other -> Pop for simplicity if we want; else leave unmapped
_add("chanson", "Pop")


def map_to_canonical(genre_list, allowed_genres):
    """
    From a list of genre strings (from MusicBrainz), return one canonical genre
    that is in allowed_genres, or None if only skip tags / empty / no match.
    """
    if not genre_list:
        return None
    # Collect all tags (lowercase), skipping non-genre
    tags = []
    for g in genre_list:
        if not g or not isinstance(g, str):
            continue
        key = g.lower().strip()
        if key in SKIP_TAGS:
            continue
        tags.append(key)
    if not tags:
        return None
    # Exact match first
    for tag in tags:
        if tag in TAG_TO_CANONICAL:
            canonical = TAG_TO_CANONICAL[tag]
            if canonical in allowed_genres:
                return canonical
    # Substring match: any tag contains or is contained by a mapping key
    for tag in tags:
        for key, canonical in TAG_TO_CANONICAL.items():
            if key in tag or tag in key:
                if canonical in allowed_genres:
                    return canonical
    return None


def main():
    with open(PATH, "r", encoding="utf-8") as f:
        artists = json.load(f)

    # Find Joker
    joker_index = None
    for i, a in enumerate(artists):
        if (a.get("name") or "").strip() == "Joker":
            joker_index = i
            break
    if joker_index is None:
        raise SystemExit("Artist 'Joker' not found in JSON.")

    # Canonical genres = exactly what appears in artists 0..Joker (inclusive)
    allowed = set()
    for a in artists[: joker_index + 1]:
        for g in a.get("genres") or []:
            if g and isinstance(g, str):
                allowed.add(g.strip())
    print(f"Canonical genres (before+including Joker): {sorted(allowed)}")
    print(f"Artists below Joker: indices {joker_index + 1} to {len(artists) - 1}\n")

    assigned = 0
    set_null = 0
    for i in range(joker_index + 1, len(artists)):
        artist = artists[i]
        raw = artist.get("genres") or []
        single = map_to_canonical(raw, allowed)
        if single is not None:
            artist["genres"] = [single]
            assigned += 1
            print(f"  {artist.get('name')}: {raw} -> [{single}]")
        else:
            artist["genres"] = []
            set_null += 1
            if raw:
                print(f"  {artist.get('name')}: {raw} -> null (no match / only skip tags)")
            else:
                print(f"  {artist.get('name')}: (empty) -> null")

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)

    print(f"\nAssigned single genre: {assigned}. Set to null: {set_null}. Saved: {PATH}")


if __name__ == "__main__":
    main()
