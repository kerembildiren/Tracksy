# Trackzy WebApp (legacy)

The **web version of Trackzy** is now served from the **Harman Games** project.

- **Run the site:** Use **HarmanGames** (sibling folder). From `Cursor_Projects/HarmanGames` run `python app.py`. The hub is at `/` and Trackzy at `/trackzy`.
- **Data:** Artist data stays in `Trackzy/DataCollection/output/artists_raw.json`. HarmanGames reads it from there (or from its own `data/artists_raw.json` if you copy it for deploy).

This WebApp folder is kept for reference and for any standalone Trackzy-only deploy. For the main Harman Games site (hub + Trackzy + SportsGuesser), use **HarmanGames**.
