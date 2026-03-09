# Data collection scripts

These scripts were used to **build and update** the artist dataset. You don’t need to run them to play the game. Keep them if you might refresh or extend the data later.

Run from the **DataCollection** directory (e.g. `python scripts/update_artists_images.py`).  
Output is written to **`output/artists_raw.json`** (the file the game uses).

---

## Build / one-time

| Script | Purpose |
|--------|---------|
| `build_turkish_artists_dataset.py` | Build the initial artist list. |

---

## Update data (re-run when you want fresh data)

| Script | Purpose | Depends on |
|--------|---------|------------|
| `update_artists_spotify_streams.py` | Fetch Spotify monthly streams (Playwright, no API key). | Playwright + Chromium |
| `update_artists_images.py` | Fetch artist image URLs from Spotify API. | Spotify API credentials |
| `update_artists_followers.py` | Fetch follower counts from Spotify API. | Spotify API credentials |
| `update_artists_preview.py` | Fetch 30s preview track per artist (top tracks or search). Stores preview_url, top_track_name, top_track_uri. | Spotify API credentials |
| `update_artists_spotify_scrape.py` | Scrape monthly listeners from artist pages (no API). | `requests` |
| `update_artists_lastfm.py` | Last.fm listeners/playcount. | Last.fm API (optional) |
| `update_artists_youtube.py` | YouTube subscriber/view counts. | YouTube API (optional) |

---

## Tidy / transform

| Script | Purpose |
|--------|---------|
| `tidy_artists_json.py` | Remove unused keys, sort by streams, set popularity = rank. Run after updating streams. |
| `remove_low_stream_artists.py` | Remove artists with &lt; 200k monthly streams; re-sort and re-assign popularity; print deleted list. |
| `discover_artists_from_playlists.py` | **Find missing artists:** reads Top 50 + Viral 50 Turkey playlists, adds any artist ID not in the JSON. Run, then run streams + preview scripts. |
| `add_artists_from_spotify.py` | **Add by name** (e.g. "Erol Evgin") when you know someone is missing. No duplicates. Then run streams + preview scripts. |

---

## Other (Excel, genres, cleanup)

Used for manual editing, genres, or one-off cleanup:

- `json_to_excel.py` – Export `artists_raw.json` to Excel.
- `excel_to_json.py` – Import from Excel back to JSON.
- `assign_single_genre.py` – Assign a single genre per artist.
- `musicbrainz_scraper.py` / `musicbrainz_genres_scraper.py` – MusicBrainz data.
- `clean_excel_and_export.py`, `cleanup_artists.py`, `cleanup_artists2.py` – Cleanup.
- `check_excel_missing.py` – Report missing fields in Excel.

---

## Testing (CLI game, no web)

- `play_game.py` – Terminal version of the game (in **DataCollection** root, not in `scripts/`).
- `test_game_logic.py` – Tests for hint/comparison logic.
