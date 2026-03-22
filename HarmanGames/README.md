# Harman Games

Main site and game hub. Pick a game from the home page; each game is a sub-project.

## Structure

```
HarmanGames/          ← You are here (main site)
  app.py              → Serves hub (/) and routes to games
  templates/          → Hub + game UIs
  static/             → Hub + Trackzy assets
  data/               → Optional copy of game data for deploy

Trackzy/              ← Sub-content: Turkish artist guess game
  DataCollection/     → Artist data (artists_raw.json)
  App/                → iOS app

SportsGuesser/        ← Sub-content: Sports guess games
  web/                → Static hub (basketball, football games)
  DataCollection/     → `output/allplayers.json`, football `superlig_data/`, `grid_game/`, `derby_challenge/`
```

## Run locally

From this folder:

```bash
cd HarmanGames
pip install -r requirements.txt
python app.py
```

Then open:

- **Hub:** http://localhost:5000/
- **Trackzy:** http://localhost:5000/trackzy
- **SportsGuesser:** http://localhost:5000/sportsguesser/
- **Football (Süper Lig grid):** http://localhost:5000/sportsguesser/football/
- **Football (Derbi Challenge):** http://localhost:5000/sportsguesser/football/derby/

**Trackzy data:** At startup, `app.py` loads `data/artists_raw.json` **if that file exists**; otherwise `../Trackzy/DataCollection/output/artists_raw.json`. For production, either keep both in the repo or copy the canonical file into `HarmanGames/data/` (see `data/README.md`).

**SportsGuesser data:** Hub static files from `../SportsGuesser/web/`. Basketball (Dart) uses `../SportsGuesser/DataCollection/output/allplayers.json`. Football grid + Derbi name suggestions use `../SportsGuesser/DataCollection/football/superlig_data/` (or env `SUPERLIG_DATA`). Derbi match rows come from `derby_challenge/bundled/derbies.json` (rebuild with `build_derby_bundle.py` after CSV updates).

Deploy on Render: root directory **`HarmanGames`**, repo root must still contain sibling **`Trackzy`** and **`SportsGuesser`** folders. See **`DEPLOY.md`**.

## Adding a new game

1. Add your game project as a sibling folder (e.g. `Cursor_Projects/MyGame/`).
2. In `app.py`, add a route (e.g. `/mygame`) and optional static/API routes.
3. In `templates/home.html`, add a new hub card linking to `{{ url_for('mygame') }}`.
