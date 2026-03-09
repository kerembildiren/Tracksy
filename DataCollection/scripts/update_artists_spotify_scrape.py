"""
Fetch Spotify monthly listeners (and followers) by scraping the public artist page.
No Spotify API or credentials needed.

Spotify no longer exposes monthly listeners via the API, but the value is visible on
the artist page (e.g. https://open.spotify.com/artist/{id}). This script loads that
page and parses the visible "X monthly listeners" and "X Followers" text.

Updates artists_raw.json with:
  - spotify_monthly_listeners (number or null)
  - followers: { "total": number } when found on the page (only if currently null)

Resume: skips artists that already have spotify_monthly_listeners set (number or null).
"""
import json
import os
import re
import time

try:
    import requests
except ImportError:
    raise SystemExit("Install requests: pip install requests")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output")
INPUT_OUTPUT_FILE = "artists_raw.json"
# Same layout for every artist: open.spotify.com/artist/{id}
SPOTIFY_ARTIST_URL = "https://open.spotify.com/artist/{id}"
SLEEP_BETWEEN_REQUESTS = 2.0  # be polite, avoid blocking
SAVE_EVERY_N = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_int_from_captured(s: str) -> int | None:
    """Convert string like '4,827,069' or '4827069' to int."""
    if s is None:
        return None
    try:
        return int(s.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def fetch_listeners_and_followers(artist_id: str) -> tuple[int | None, int | None]:
    """
    Load artist page and extract monthly listeners and followers from the page.
    Returns (monthly_listeners, followers_total). Either can be None if not found.
    """
    url = SPOTIFY_ARTIST_URL.format(id=artist_id)
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        text = r.text
    except Exception:
        return None, None

    monthly_listeners = None
    followers_total = None

    # 1) Visible text on page: "4,827,069 monthly listeners" and "1,875,481 Followers"
    #    (locale can vary; try both with and without comma in number)
    visible_listeners = re.search(
        r"([\d,]+)\s*monthly\s*listeners",
        text,
        re.IGNORECASE,
    )
    if visible_listeners:
        monthly_listeners = _parse_int_from_captured(visible_listeners.group(1))

    visible_followers = re.search(
        r"([\d,]+)\s*Followers",
        text,
    )
    if visible_followers:
        followers_total = _parse_int_from_captured(visible_followers.group(1))

    # 2) Fallback: embedded JSON / script patterns (Spotify sometimes embeds data)
    if monthly_listeners is None:
        for pattern in [
            r'"monthlyListeners"\s*:\s*(\d+)',
            r'"monthly_listeners"\s*:\s*(\d+)',
            r'"listeners"\s*:\s*(\d+)',
            r'["\']monthlyListeners["\']\s*:\s*(\d+)',
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                monthly_listeners = _parse_int_from_captured(m.group(1))
                break

    if followers_total is None:
        for pattern in [
            r'"followers"\s*:\s*\{\s*"total"\s*:\s*(\d+)',
            r'"total"\s*:\s*(\d+)\s*[,\}].*?[Ff]ollowers',
        ]:
            m = re.search(pattern, text)
            if m:
                followers_total = _parse_int_from_captured(m.group(1))
                break

    return monthly_listeners, followers_total


def main() -> None:
    path = os.path.join(OUTPUT_DIR, INPUT_OUTPUT_FILE)
    if not os.path.isdir(OUTPUT_DIR):
        raise SystemExit(f"Output directory not found: {OUTPUT_DIR}")

    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)

    if not artists:
        print("No artists in file. Exiting.")
        return

    # Only fetch artists that don't have spotify_monthly_listeners set yet (resume-friendly)
    to_fetch = [
        (i, a) for i, a in enumerate(artists)
        if a.get("spotify_monthly_listeners") is None
    ]
    if not to_fetch:
        print("All artists already have spotify_monthly_listeners. Nothing to do.")
        return

    total = len(to_fetch)
    print(f"Scraping monthly listeners (and followers) for {total} artists from Spotify artist pages.")
    print("No API key required. One request per artist.")

    updated_listeners = 0
    updated_followers = 0
    for k, (idx, artist) in enumerate(to_fetch):
        aid = (artist.get("id") or "").strip()
        if not aid:
            artist["spotify_monthly_listeners"] = None
        else:
            monthly, followers = fetch_listeners_and_followers(aid)
            artist["spotify_monthly_listeners"] = monthly
            if monthly is not None:
                updated_listeners += 1
            # Set followers from page only when not already set (e.g. from API)
            if followers is not None and artist.get("followers") is None:
                artist["followers"] = {"total": followers}
                updated_followers += 1
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if (k + 1) % SAVE_EVERY_N == 0 or (k + 1) == total:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(artists, f, ensure_ascii=False, indent=2)
            print(f"  Processed {k + 1}/{total} (saved), monthly listeners: {updated_listeners}, followers: {updated_followers}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)
    print(f"Done. spotify_monthly_listeners: {updated_listeners}/{total}, followers from page: {updated_followers}. Saved to {path}")


if __name__ == "__main__":
    main()
