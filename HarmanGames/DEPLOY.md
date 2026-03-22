# Deploy Harman Games to Render (harmangaming.com)

Your site should behave like local:

- **Hub:** https://harmangaming.com/
- **Trackzy:** https://harmangaming.com/trackzy
- **SportsGuesser:** https://harmangaming.com/sportsguesser/
- **Football (Süper Lig grid):** https://harmangaming.com/sportsguesser/football/
- **Football (Derbi Challenge):** https://harmangaming.com/sportsguesser/football/derby/

---

## 1. GitHub: one repo with all three projects

Render will run the **HarmanGames** app, but the app expects **Trackzy** and **SportsGuesser** as **sibling folders** (so it can read Trackzy data and serve SportsGuesser).

Your repo **root** must look like this:

```
your-repo/
├── HarmanGames/       ← app, templates, static, requirements.txt
├── Trackzy/           ← DataCollection/output/artists_raw.json (+ App, WebApp if you keep them)
├── SportsGuesser/    ← web/, DataCollection/output/allplayers.json
└── (optional: README at root)
```

So you have two options:

**Option A – Same repo you use now (e.g. “Trackzy” repo)**  
Rename or restructure so the **root** contains three folders: `HarmanGames`, `Trackzy`, `SportsGuesser`.  
Example: if the repo is currently “Trackzy” with Trackzy’s contents at root, create a new root and move the current content into `Trackzy/`, then add `HarmanGames/` and `SportsGuesser/` at the same level.

**Option B – New repo (e.g. “harman-games” or “harmangaming”)**  
Create a new repo and push **only** these three folders (and an optional root README):

- Copy or clone `HarmanGames`, `Trackzy`, and `SportsGuesser` from your machine into one folder, then push that as the repo root.

Make sure in the repo you have:

- `HarmanGames/app.py`, `requirements.txt`, `templates/`, `static/`
- Trackzy artist JSON: **`HarmanGames/data/artists_raw.json` takes precedence** if that file exists in the repo; otherwise `Trackzy/DataCollection/output/artists_raw.json` (see `HarmanGames/data/README.md`). At least one must be present.
- `SportsGuesser/web/` (e.g. `index.html`, `css/`, `js/`) and `SportsGuesser/DataCollection/output/allplayers.json`
- `SportsGuesser/DataCollection/football/superlig_data/` — **required** for the Süper Lig grid (`/sportsguesser/football/`) and for **player name autocomplete** in Derbi Challenge (same player index as the grid). The app loads CSVs from this folder (or set `SUPERLIG_DATA` on the server to an absolute path). Without it, the football grid may error when building the player index; Derbi may load match data but suggestions can fail.
- `SportsGuesser/DataCollection/football/derby_challenge/bundled/derbies.json` — **commit this file** in the repo. It is pre-built public match stats (scores, goals, cards, substitutions) for FB–GS–BJK–TS derbies; the game reads it at runtime (no CSV scan). It contains no API keys or secrets. To regenerate after updating `superlig_data`, run `python build_derby_bundle.py` inside `derby_challenge/`.

If `artists_raw.json` or `allplayers.json` are in `.gitignore`, either remove them from `.gitignore` for this repo or add a build step that creates them (e.g. copy from another source); otherwise the deployed app will not find the data.

---

## 2. Render: point the service at HarmanGames

1. Go to [Render Dashboard](https://dashboard.render.com) and open the service that is used for harmangaming.com (or create a new **Web Service**).
2. Connect it to the GitHub repo that has the structure above.
3. **Root Directory**  
   Set to: **`HarmanGames`**  
   So Render builds and runs from the `HarmanGames` folder; the repo root (parent of `HarmanGames`) still contains `Trackzy` and `SportsGuesser`, which the app uses via `../Trackzy` and `../SportsGuesser`.
4. **Runtime:** Python 3.
5. **Build Command** (optional if auto-detect works):  
   `pip install -r requirements.txt`
6. **Start Command:**  
   `gunicorn --bind 0.0.0.0:$PORT app:app`  
   (Render sets `PORT`; this makes the server listen on it.)
7. **Environment variables (optional):**
   - `SECRET_KEY` – set a long random string in Render; the app can read it with `os.environ.get('SECRET_KEY', 'default-dev-key')` and use it for `app.secret_key` in production.
8. Save. Render will build and deploy. The app will use `../Trackzy` and `../SportsGuesser` relative to `HarmanGames`, so the same logic as local.

---

## 3. Custom domain (harmangaming.com)

- In Render, open your Web Service → **Settings** → **Custom Domains**.
- Add **harmangaming.com** and, if you want, **www.harmangaming.com**.
- In your domain registrar (e.g. Cloudflare), point the domain to the host Render gives you (CNAME or A record as instructed). No code changes needed for the domain.

---

## 4. After deploy

- **Hub:** https://harmangaming.com/  
- **Trackzy:** https://harmangaming.com/trackzy  
- **SportsGuesser:** https://harmangaming.com/sportsguesser/

If the hub loads but Trackzy fails (e.g. “Artist data not found”), check that `Trackzy/DataCollection/output/artists_raw.json` is in the repo and not ignored. If SportsGuesser fails, check that `SportsGuesser/web/` and `allplayers.json` are present and not ignored. If the football grid fails on first load, ensure `SportsGuesser/DataCollection/football/superlig_data/` is deployed (or `SUPERLIG_DATA` points to it). If Derbi Challenge returns “Derbi verisi yok”, ensure `bundled/derbies.json` is in the repo and deployed. **Flask URL routing:** `HarmanGames/app.py` registers blueprints for `/sportsguesser/football/` and `/sportsguesser/football/derby/` before the catch-all `sportsguesser/<path>` static handler; keep that order so the hub and games are not served from the wrong folder.
