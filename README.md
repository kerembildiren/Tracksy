# Cursor_Projects

This folder is your workspace. Each subfolder is a separate project.

## Projects

- **HarmanGames** – Main site (hub). Run `python app.py` from HarmanGames to serve the home page and all games. Contains the hub UI and routes to Trackzy and SportsGuesser.
- **Trackzy** – Game: Turkish artist guess. Data in DataCollection; iOS app in App. Web version is served via HarmanGames at `/trackzy`.
- **SportsGuesser** – Game: Sports/player guess. Web app in `web/`; served via HarmanGames at `/sportsguesser/`.

## Run the site

```bash
cd HarmanGames
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000/ (hub), http://localhost:5000/trackzy, or http://localhost:5000/sportsguesser/.

## Adding new projects

Create a new folder here (e.g. `MyNewApp`) and put your project files inside it. To add a new **game** to Harman Games, add it as a sibling folder and register its route and hub card in HarmanGames.
