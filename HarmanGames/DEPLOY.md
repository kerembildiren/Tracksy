# Deploy Harman Games to Render (harmangaming.com)

Your site should behave like local:

- **Hub:** https://harmangaming.com/
- **Trackzy:** https://harmangaming.com/trackzy
- **SportsGuesser:** https://harmangaming.com/sportsguesser/

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
- `Trackzy/DataCollection/output/artists_raw.json` (the game needs this file)
- `SportsGuesser/web/` (e.g. `index.html`, `css/`, `js/`) and `SportsGuesser/DataCollection/output/allplayers.json`

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

If the hub loads but Trackzy fails (e.g. “Artist data not found”), check that `Trackzy/DataCollection/output/artists_raw.json` is in the repo and not ignored. If SportsGuesser fails, check that `SportsGuesser/web/` and `allplayers.json` are present and not ignored.
