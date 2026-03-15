# Game data (for deployment)

The game reads the artist list from **`artists_raw.json`** in this folder.

- **Local development:** If this file is missing, the app falls back to `../DataCollection/output/artists_raw.json`, so you don’t need to copy anything.
- **Deployment (e.g. Render, GitHub, server):** Copy the data file here so the WebApp is self-contained (from repo root: `cp DataCollection/output/artists_raw.json WebApp/data/artists_raw.json`). Then commit, push, and redeploy. On Render the app uses this file when DataCollection is not in the deploy.

See **ROADMAP.md** in the project root for what to upload and what is only used for data collection.
