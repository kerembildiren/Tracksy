# Data Collection Scripts

Python scripts for collecting and updating Turkish artist data.

## Setup

```bash
cd DataCollection
pip install -r requirements.txt
```

## Scripts

| Script | Purpose |
|--------|---------|
| `build_turkish_artists_dataset.py` | Main script to build initial dataset |
| `update_artists_lastfm.py` | Update Last.fm listener data |
| `update_artists_spotify_scrape.py` | Scrape Spotify monthly listeners |
| `update_artists_youtube.py` | Update YouTube subscriber data |
| `update_artists_followers.py` | Update follower counts |

## Output

Generated files are saved to `output/`:
- `artists_raw.json` - Full artist dataset

## Updating the iOS App

After updating the dataset, copy to the iOS app resources:

```bash
cp output/artists_raw.json ../App/TurkishSingerGuess/Resources/artists.json
```

## Data Schema

```json
{
  "id": "spotify_id",
  "name": "Artist Name",
  "genres": ["genre1", "genre2"],
  "followers": { "total": 12345 },
  "debut": 2010,
  "nationality": "Turkish",
  "lastfm_listeners": 100000,
  "lastfm_playcount": 5000000,
  "spotify_monthly_listeners": 500000,
  "popularity": 75
}
```

## Future Data Fields

The following fields should be added for full game functionality:
- `debut_year` - Year the artist started
- `group_size` - "Solo", "Duo", or "Group"
- `gender` - "Male", "Female", or "Mixed"
- `monthly_listeners` - Primary listener count metric
