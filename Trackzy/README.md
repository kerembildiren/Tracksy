# Tracksy

A daily guessing game for Turkish singers (Spotle-style). Web version — play in the browser.

## Quick start (local)

```bash
cd WebApp
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. The app loads artist data from `DataCollection/output/artists_raw.json` (or `WebApp/data/artists_raw.json` if you put it there).

---

## Pushing to GitHub

1. **Create a new repository on GitHub**  
   - Go to [github.com/new](https://github.com/new).  
   - Name it e.g. `tracksy` or `tracksy-game`.  
   - Do **not** add a README, .gitignore, or license (you already have them).  
   - Create the repo.

2. **From your project folder, run:**

```bash
cd C:\Users\4\Desktop\Cursor_Projects

git init
git add .
git commit -m "Initial commit: Tracksy web game"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub username and repo name.

3. **What gets committed**  
   - `WebApp/` — Flask app (game logic, templates, static files).  
   - `DataCollection/output/artists_raw.json` — artist data (the game uses this if `WebApp/data/artists_raw.json` is missing).  
   - `DataCollection/` — scripts and docs (optional for running the game; useful if you update data later).  
   - `.gitignore` — excludes `__pycache__`, `venv`, `.env`, and similar.

---

## Deploying to a hosting site

After the repo is on GitHub you can connect it to a host (e.g. Render, Railway, PythonAnywhere, Fly.io).

- **Build command:** (often not needed; some hosts detect Flask.)  
- **Start command:** e.g. `python app.py` or `gunicorn app:app` (if you add gunicorn).  
- **Root / app directory:** set to `WebApp` so the host runs from there.  
- The app will look for `WebApp/data/artists_raw.json` first; if you didn’t add that, copy `DataCollection/output/artists_raw.json` into `WebApp/data/artists_raw.json` in the repo so the deployed app finds the data.

**Production:** Set a secret key via environment variable instead of the default in code, e.g. `FLASK_SECRET_KEY` or `SECRET_KEY`, and read it in `app.py` so the host can inject it.

---

## Project structure

```
├── WebApp/                    # Web game (Flask)
│   ├── app.py
│   ├── requirements.txt
│   ├── static/, templates/
│   └── data/                  # optional: artists_raw.json for deploy
├── DataCollection/
│   ├── output/artists_raw.json   # artist data (used by game if WebApp/data/ missing)
│   └── scripts/                  # scripts to build/update data
├── .gitignore
└── README.md
```

---

## Game rules

- One correct artist per day (same for everyone).
- Up to 10 guesses; after each guess you get hints comparing your guess to the correct artist.
- Hints: debut year (higher/lower), group size, gender, genre, nationality, popularity rank (higher/lower, “close” within 15 ranks).

---

## Updating artist data

Scripts and instructions are in `DataCollection/` and `DataCollection/scripts/README.md`. After updating `DataCollection/output/artists_raw.json`, either commit and push so the deployed app gets it, or copy that file to `WebApp/data/artists_raw.json` and redeploy.
