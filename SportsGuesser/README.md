# SportsGuesser

Sports guessing games using data from `DataCollection/output/allplayers.json`.

## Run the game

### Production-style (recommended — same as harmangaming.com)

From the **HarmanGames** folder (sibling of `SportsGuesser`):

```bash
cd HarmanGames
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000/** → SportsGuesser → Football (Süper Lig grid or Derbi Challenge), or directly **http://localhost:5000/sportsguesser/football/** or **http://localhost:5000/sportsguesser/football/derby/**.

Derbi maç verisi: `DataCollection/football/derby_challenge/bundled/derbies.json` (üretmek için `derby_challenge/build_derby_bundle.py`).

### Static SportsGuesser only (basketball UI)

From the **SportsGuesser** project root:

```bash
cd SportsGuesser
python server.py
```

Then open **http://localhost:8080**. Basketball / Dart works; **Football** links to `/sportsguesser/football/` and needs the HarmanGames app above for the Flask API.

### Süper Lig grid alone (dev)

```bash
cd SportsGuesser/DataCollection/football/grid_game
python app.py
```

Default: **http://localhost:5050/**. Data: `../superlig_data/` or env `SUPERLIG_DATA`.

- **Home**: choose Basketball or Football.
- **Basketball**: **Dart** — two players from 501; valid guesses reduce score. First to 0 wins.
- **Football**: 3×3 Süper Lig player grid (teams / countries); see `DataCollection/football/grid_game/`.

## Data

Player data is in `DataCollection/output/allplayers.json`. Update it with the scripts in `DataCollection/` (see `DataCollection/README.md`).
