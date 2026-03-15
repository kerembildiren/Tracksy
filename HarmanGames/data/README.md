# Game data (optional)

- **Trackzy:** The app reads artist data from `artists_raw.json` in this folder first. If missing, it uses `../Trackzy/DataCollection/output/artists_raw.json`.
- **SportsGuesser:** Served from the `../SportsGuesser` project; no data files needed here.

## Updating artist data (artists_raw.json)

When you change the artist data (e.g. genres, debut year, new artists):

1. **Edit the source file:** `Trackzy/DataCollection/output/artists_raw.json`
2. **Copy into this folder** so the live app (e.g. Render) gets the update:
   ```bash
   # From repo root (Cursor_Projects or Tracksy)
   cp Trackzy/DataCollection/output/artists_raw.json HarmanGames/data/artists_raw.json
   ```
3. **Push and redeploy:**
   ```bash
   git add Trackzy/DataCollection/output/artists_raw.json HarmanGames/data/artists_raw.json
   git commit -m "Update artist data (artists_raw.json)"
   git push
   ```
   Then trigger a redeploy on Render (or wait for auto-deploy). The app loads the JSON at startup, so the new data is used immediately after redeploy.
