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

SportsGuesser/        ← Sub-content: Sports guess game
  web/                → Static frontend
  DataCollection/     → Player data
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

Artist data is read from `../Trackzy/DataCollection/output/artists_raw.json`. For a deploy without the Trackzy folder, copy that file to `data/artists_raw.json`.

## Adding a new game

1. Add your game project as a sibling folder (e.g. `Cursor_Projects/MyGame/`).
2. In `app.py`, add a route (e.g. `/mygame`) and optional static/API routes.
3. In `templates/home.html`, add a new hub card linking to `{{ url_for('mygame') }}`.
