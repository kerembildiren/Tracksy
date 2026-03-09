"""
Assign a single generic genre to each artist based on their existing MusicBrainz genres.
Maps specific tags (e.g. "abstract hip hop", "grunge") to broad categories: Pop, Rap, Rock, Metal, etc.
Updates artists_raw.json in place.
"""
import json
import os

# Generic genre categories (order = priority when multiple match; first wins)
GENERIC_GENRES = [
    "Metal", "Rap", "Rock", "Pop", "R&B", "Electronic", "Jazz", "Folk", "Classical",
    "Reggae", "Punk", "World"
]

# Map lowercase genre/tag strings to generic category.
# More specific terms first so we can match "doom metal" -> Metal before "metal" -> Metal.
SPECIFIC_TO_GENERIC = {}

def _add_mapping(category, *terms):
    for t in terms:
        SPECIFIC_TO_GENERIC[t.lower().strip()] = category

# Metal (check before Rock)
_add_mapping("Metal", "metal", "heavy metal", "doom metal", "nu metal", "traditional doom metal", "turkish heavy-metal")

# Rap / Hip-hop
_add_mapping("Rap", "hip hop", "hip-hop", "rap", "trap", "cloud rap", "pop rap", "boom bap", "grime",
     "deutschrap", "memphis rap", "southern hip hop", "hardcore hip hop", "instrumental hip hop",
     "alternative hip hop", "abstract hip hop", "underground hip hop", "crunk", "dirty south",
     "turkish hip hop", "turkish rap", "türkçe rap")

# Rock
_add_mapping("Rock", "rock", "alternative rock", "grunge", "indie rock", "folk rock", "pop rock",
     "psychedelic rock", "progressive rock", "anatolian rock", "adult alternative pop/rock",
     "alternative/indie rock", "heavy psych", "indie surf", "turkish alternative")

# Punk
_add_mapping("Punk", "pop punk", "ska punk", "rapcore")

# Pop
_add_mapping("Pop", "pop", "dance-pop", "teen pop", "indie pop", "schlager", "traditional pop",
     "arabesk", "fantezi", "deep turkish pop", "turkish pop", "turkish pop music",
     "turkish pop singers", "girl group", "eurovision", "alternative pop")

# R&B / Soul / Gospel
_add_mapping("R&B", "r&b", "rhythm and blues", "rhythm & blues", "soul", "gospel", "black gospel",
     "pop soul", "classic soul", "southern soul", "early r&b", "standards")

# Electronic / Dance
_add_mapping("Electronic", "electronic", "dance", "dubstep", "drum and bass", "uk garage")

# Jazz
_add_mapping("Jazz", "jazz", "vocal jazz")

# Folk
_add_mapping("Folk", "folk", "turkish folk", "turkish folk music", "breton")

# Classical
_add_mapping("Classical", "classical", "chamber orchestra", "turkish classical")

# Reggae
_add_mapping("Reggae", "reggae", "dancehall")

# World (catch regional/cultural that don't fit above)
_add_mapping("World", "j-pop", "j-rock", "visual kei", "osare kei", "anime", "soft visual")

# Skip: artist names, placeholders, non-music (turkish, american, german, cypriot, uk, etc. as sole tag)
# "singer-songwriter" -> could be Pop or Folk; treat as Pop
_add_mapping("Pop", "singer-songwriter")

# Noise, experimental -> Rock for simplicity
_add_mapping("Rock", "noise", "experimental")

# Remove the helper from namespace
del _add_mapping

# Artist name / non-genre tags to ignore when choosing (so we don't map "teoman" -> something)
SKIP_TAGS = {
    "turkish", "american", "german", "english", "japanese", "cypriot", "uk", "bristol",
    "sezen aksu", "teoman", "şebnem ferah", "nilüfer", "zakkum", "anakin artz", "artz",
    "aslı", "damar", "normlife", "boğver", "komşu", "türkçe",
    "producer", "author", "writer", "on writing", "protest",
    "arts", "fantasy", "horror", "anime", "audio drama", "audiobook",
    "has german audio plays", "has german audiobooks", "added for google code-in 2016",
    "2010s", "3850 records", "_edit", "italian orchestra"
}


def pick_single_generic_genre(genre_list):
    """
    From a list of specific genres (from MusicBrainz), return one generic genre.
    Uses GENERIC_GENRES priority order: e.g. Metal wins over Rock if both match.
    Skips non-genre tags (artist names, etc.).
    """
    if not genre_list:
        return None
    # Build set of generics that match any of this artist's tags
    matched = set()
    for g in genre_list:
        if not g or not isinstance(g, str):
            continue
        key = g.lower().strip()
        if key in SKIP_TAGS:
            continue
        if key in SPECIFIC_TO_GENERIC:
            matched.add(SPECIFIC_TO_GENERIC[key])
        else:
            for spec, generic in SPECIFIC_TO_GENERIC.items():
                if spec in key or key in spec:
                    matched.add(generic)
                    break
    # Return highest-priority generic that matched
    for generic in GENERIC_GENRES:
        if generic in matched:
            return generic
    return None


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "output", "artists_raw.json")

    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    updated = 0
    no_genre = 0
    for artist in artists:
        raw = artist.get("genres") or []
        single = pick_single_generic_genre(raw)
        if single:
            artist["genres"] = [single]
            updated += 1
        else:
            artist["genres"] = []
            if raw:
                no_genre += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, indent=2, ensure_ascii=False)

    print(f"Assigned single generic genre to {updated} artists.")
    print(f"Unmapped (genres set to []): {no_genre} artists with only non-music/skip tags.")
    print(f"Output: {path}")


if __name__ == "__main__":
    main()
