# SportsGuesser – Data collection

Scripts and output for building game data. **Basketball and football are kept strictly separate.**

## Layout

```
DataCollection/
├── basketball/
│   ├── scripts/          # fetch_30plus_games.py, fetch_triple_doubles.py
│   └── output/           # allplayers.json, basketball_30plus_2026.json
├── football/
│   ├── scripts/          # fetch_super_lig_standings.py, team_excels_to_json.py
│   ├── output/           # super_lig/ (seasons, all_teams.json, etc.)
│   └── TeamExcels/       # Your uploaded team (and later player) Excel files
├── requirements.txt
└── README.md
```

The web app loads basketball data from `basketball/output/allplayers.json`.

---

## Basketball

### 30+ and 40+ point games

Fetches seasons 2026 down to 1980 from Land of Basketball, merges by player name, saves after each year.

```bash
cd DataCollection
pip install -r requirements.txt
playwright install chromium
python basketball/scripts/fetch_30plus_games.py
```

Optional: `--start-year`, `--end-year`. Output: `basketball/output/allplayers.json`.

### Triple-doubles

Fetches triple-doubles by season and merges into `allplayers.json`.

```bash
python basketball/scripts/fetch_triple_doubles.py
```

---

## Football (Super Lig)

### Standings (FBRef)

Fetches Turkish Super Lig standings (2001-2002 through 2024-2025). Saves per-season JSON and `all_teams.json` under `football/output/super_lig/`.

```bash
python football/scripts/fetch_super_lig_standings.py
```

Options: `--start`, `--end`, `--debug`, `--headed`, `--use-chrome` (use your Chrome profile if logged in to FBRef).

### Team Excels → JSON

Converts Excel files in `football/TeamExcels/` to JSON (for team data; player Excels later).

```bash
python football/scripts/team_excels_to_json.py
```

Output: `football/TeamExcels/json/` (when conversion is enabled).
