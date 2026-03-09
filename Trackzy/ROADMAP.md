# Turkish Singer Guess – File System & Deployment Roadmap

This document clarifies **what runs the game** vs **what was used to build/update data**, and what you need for GitHub or a server.

---

## Data flow (no fetching while playing)

- **Web:** The game reads a single JSON file (`WebApp/data/artists_raw.json` or `DataCollection/output/artists_raw.json`). There is **no** API or network call during play.
- **Mobile:** The app reads from the **bundled** file `artists.json` in the app bundle (copied from `artists_raw.json`). There is **no** network fetch when playing.
- **When you update the data:** Regenerate or edit `DataCollection/output/artists_raw.json`, then:
  - **Web:** Copy it to `WebApp/data/artists_raw.json` if you use that for deploy; refresh the server or reload.
  - **Mobile:** Copy to `App/TurkishSingerGuess/Resources/artists.json` and rebuild the app.

So: **whoever downloads the game (web or app) uses the JSON you shipped; no live fetching.**

---

## 1. What You Need to RUN the Game

Only these are required for others to play:

| Item | Location | Purpose |
|------|----------|---------|
| **Web game** | `WebApp/` | Flask app: `app.py`, `templates/`, `static/` (CSS, JS), `requirements.txt` |
| **Artist data** | One JSON file | The game reads `artists_raw.json` (259 artists with name, popularity, image_url, etc.) |

**How the app finds the data (see below):**  
It first looks for `WebApp/data/artists_raw.json`. If that exists, it uses it (good for deployment). Otherwise it falls back to `DataCollection/output/artists_raw.json` (good for local dev).

**To run locally (current setup):**
```bash
cd WebApp
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```
No need to move anything: the app will use `DataCollection/output/artists_raw.json` if `WebApp/data/artists_raw.json` is missing.

---

## 2. What to Upload to GitHub / Server (for others to play)

**Option A – Minimal (recommended for “just the game”):**

- Upload the **WebApp** folder.
- Put the artist data inside it so the game is self-contained:
  - Copy `DataCollection/output/artists_raw.json` → `WebApp/data/artists_raw.json`.
- Then your repo (or server) only needs:
  ```
  WebApp/
  ├── app.py
  ├── requirements.txt
  ├── data/
  │   └── artists_raw.json
  ├── static/
  └── templates/
  ```
- No need to upload **DataCollection** or **App** for the web game.

**Option B – Full repo (for you + future mobile):**

- Upload **WebApp** (with `data/artists_raw.json` as above).
- Upload **App/** (iOS/Swift) if you want the mobile project in the same repo.
- You can still keep **DataCollection** in the repo but **do not need it** for running the game; it’s only for rebuilding/updating data.

**What to exclude (e.g. in .gitignore):**

- `DataCollection/.cache/`
- Python `__pycache__/`, `venv/`, `.env`
- Any file with API keys or secrets

---

## 3. Data Pipeline (One-Time or Occasional – Not Needed to Run the Game)

Everything under **DataCollection** was used to **build or update** the artist list. You don’t need to run these to play the game; keep them only if you might refresh data later.

| Category | Scripts / Files | When to use |
|----------|-----------------|-------------|
| **Output (used by game)** | `DataCollection/output/artists_raw.json` | This is the file the game reads (via WebApp/data copy or fallback). |
| **Build / one-time** | `scripts/build_turkish_artists_dataset.py` | Initial dataset creation. |
| **Update data (run when you want fresh data)** | `scripts/update_artists_spotify_streams.py` | Monthly streams (Playwright). |
| | `scripts/update_artists_images.py` | Artist images (Spotify API). |
| | `scripts/update_artists_followers.py` | Followers (Spotify API; optional). |
| | `scripts/update_artists_spotify_scrape.py` | Scrape listeners (no API). |
| | `scripts/update_artists_lastfm.py` | Last.fm data. |
| | `scripts/update_artists_youtube.py` | YouTube data. |
| **Tidy / transform** | `scripts/tidy_artists_json.py` | Remove keys, sort by streams, set popularity rank. |
| **Excel ↔ JSON** | `json_to_excel.py`, `excel_to_json.py` | Export/import for manual editing. |
| **Other data tools** | `assign_single_genre.py`, `musicbrainz_scraper.py`, `musicbrainz_genres_scraper.py` | Genres / MusicBrainz. |
| | `clean_excel_and_export.py`, `cleanup_artists.py`, `cleanup_artists2.py`, `check_excel_missing.py` | Cleanup and checks. |
| **Testing / CLI** | `play_game.py`, `test_game_logic.py` | CLI game and logic tests. |

See **DataCollection/scripts/README.md** for a short description of each script.

---

## 4. Mobile App (Future)

- **App/TurkishSingerGuess/** is the iOS app (Swift).
- It uses its own copy of the data: **App/TurkishSingerGuess/Resources/artists.json**.
- To update the mobile app after changing data:
  ```bash
  cp DataCollection/output/artists_raw.json App/TurkishSingerGuess/Resources/artists.json
  ```
- For “what to upload for the mobile app,” you only need the **App/** project and that `artists.json` (or the same data in the format the app expects).

---

## 5. Summary

- **To run the game (web):** Use **WebApp** + one **artists_raw.json** (in `WebApp/data/` for deploy, or `DataCollection/output/` for local).
- **To put the game on GitHub/server:** Upload **WebApp** and put **artists_raw.json** in **WebApp/data/** so the game is self-contained; DataCollection is optional.
- **DataCollection** = scripts and pipeline for building/updating data; keep them if you might need to refresh data, but they are not required to run the game.
- **Mobile:** Use **App/** and sync **artists.json** from `DataCollection/output/artists_raw.json` when you update data.

---

## UI workflow: where to design first

- **You don’t need a separate design tool or environment.** Use the **WebApp** as your design reference.
- **Suggested flow:** Add and refine UI in the **WebApp** first (menus, home screen, buttons, layout, copy). When you’re happy with the flow and look, **replicate that structure and styling in the iOS app** (SwiftUI). Same project; WebApp = prototype, App = native implementation.
- **Menus and flow:** If you want a home screen with “Play”, “How to play”, “Stats”, add that flow in the WebApp first, then mirror it in the app (e.g. HomeView → Play → GameView).
