"""
Remove artists by exact name from artists_raw.json. Prints removed names.
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(SCRIPT_DIR, "..", "output", "artists_raw.json")

NAMES_TO_REMOVE = {
    "Kerim Tekin",
    "Nil Burak",
    "Berksan",
    "Yeliz",
    "Marc Aryan",
    "Asu Maralman",
    "Betül Demir",
    "Belkıs Özener",
    "Nesrin Sipahi",
    "Pois",
    "Seyyal Taner",
}


def main():
    with open(PATH, "r", encoding="utf-8") as f:
        artists = json.load(f)
    before = len(artists)
    kept = [a for a in artists if (a.get("name") or "").strip() not in NAMES_TO_REMOVE]
    removed = [a for a in artists if (a.get("name") or "").strip() in NAMES_TO_REMOVE]
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    print(f"Removed {len(removed)} artists. Before: {before}, after: {len(kept)}.")
    for a in removed:
        print(f"  - {a.get('name')}")


if __name__ == "__main__":
    main()
