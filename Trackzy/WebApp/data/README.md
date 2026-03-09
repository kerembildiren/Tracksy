# Game data (for deployment)

The game reads the artist list from **`artists_raw.json`** in this folder.

- **Local development:** If this file is missing, the app falls back to `../DataCollection/output/artists_raw.json`, so you don’t need to copy anything.
- **Deployment (e.g. GitHub, server):** Copy the data file here so the WebApp is self-contained:
  ```bash
  cp ../DataCollection/output/artists_raw.json artists_raw.json
  ```
  Then deploy the whole **WebApp** folder (including `data/artists_raw.json`).

See **ROADMAP.md** in the project root for what to upload and what is only used for data collection.
