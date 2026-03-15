# SportsGuesser

Sports guessing games using data from `DataCollection/output/allplayers.json`.

## Run the game

From the **SportsGuesser** project root (the folder that contains `server.py` and `web/`):

```bash
cd C:\Users\4\Desktop\Cursor_Projects\SportsGuesser
python server.py
```

If you’re already inside `SportsGuesser\DataCollection`, go up first: `cd ..` then `python server.py`.

Then open **http://localhost:8080** in your browser.

- **Home**: choose Basketball (Football coming soon).
- **Basketball**: choose **Dart**.
- **Dart**: two players, start at 501. Each turn, guess an NBA player; their career 30+ point games count is deducted if the guess is valid (≤ 180 and ≤ your current score). First to exactly 0 wins.

## Data

Player data is in `DataCollection/output/allplayers.json`. Update it with the scripts in `DataCollection/` (see `DataCollection/README.md`).
