# Game data (optional)

- **Trackzy:** The app reads artist data from `artists_raw.json` in this folder first. If missing, it uses `../Trackzy/DataCollection/output/artists_raw.json`.
- **SportsGuesser:** Served from the `../SportsGuesser` project; no data files needed here.

## Updating artist data (artists_raw.json)

**Important:** The live site (e.g. harmangaming.com/trackzy) loads `artists_raw.json` from **this folder** (`HarmanGames/data/`). It does **not** read from `Trackzy/DataCollection/output/` on the server. So after you edit the source file, you must **copy it here and push both** for the live app to see the change.

### Standard procedure (e.g. monthly updates)

1. **Edit the source file only:**  
   `Trackzy/DataCollection/output/artists_raw.json`

2. **Copy into this folder** (so the deploy uses it):
   ```bash
   # From repo root (Cursor_Projects or Tracksy)
   cp Trackzy/DataCollection/output/artists_raw.json HarmanGames/data/artists_raw.json
   ```
   (PowerShell: `Copy-Item Trackzy\DataCollection\output\artists_raw.json HarmanGames\data\artists_raw.json -Force`)

3. **Push both files:**
   ```bash
   git add Trackzy/DataCollection/output/artists_raw.json HarmanGames/data/artists_raw.json
   git commit -m "Update artist data (artists_raw.json)"
   git push
   ```

4. **Redeploy** on Render (or wait for auto-deploy). The app loads the JSON **once at startup**; the new data is used after the new deploy finishes.
