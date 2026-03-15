# SportsGuesser – Data collection

Scripts and output for building the basketball (and later football) game database.  
**The game uses data from `output/allplayers.json` only.**

## Layout

- **scripts/** – Python scrapers (e.g. Land of Basketball 30+ / 40+ point games)
- **output/allplayers.json** – single JSON file updated by scripts; id, 30plus_games, 40plus_games (career totals)

## 30+ and 40+ point games (basketball)

Fetches seasons 2026 down to 1980 from Land of Basketball, merges by player name, saves after each year. Output is sorted by 30plus_games (highest first).

```bash
cd DataCollection
pip install -r requirements.txt
playwright install chromium
python scripts/fetch_30plus_games.py
```

To add only 2019–1980 (e.g. you already have 2026–2020):

```bash
python scripts/fetch_30plus_games.py --start-year 2019 --end-year 1980
```

Output: `output/allplayers.json`. Progress is printed and the file is saved after each year.

### Triple-doubles (basketball)

Fetches triple-doubles by season (same year range: 2026 down to 1980), merges into `allplayers.json` (adds/updates `triple_doubles` per player). Prints fetched data to console each year.

```bash
python scripts/fetch_triple_doubles.py
```

Optional: `--start-year`, `--end-year`. Existing `30plus_games` and `40plus_games` are preserved.
