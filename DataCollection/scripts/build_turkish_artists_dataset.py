import argparse
import json
import os
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials


GENRE_QUERIES_DEFAULT: List[str] = [
    "turkish pop",
    "turkish hip hop",
    "turkish rap",
    "turkish rock",
    "turkish indie",
    "turkish alternative",
    "turkish arabesk",
    "turkish folk",
    "turkish trap",
    "turkish jazz",
    "turkish metal",
    "turkish electronic",
    "turkish edm",
    "turkish singer-songwriter",
    "turkish soundtrack",
    "turkish classical",
    "anatolian rock",
    "turkish psychedelic rock",
]


T = TypeVar("T")


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing required environment variable: {name}\n"
            "Set Spotify credentials first:\n"
            '  PowerShell:\n'
            '    $env:SPOTIPY_CLIENT_ID="..."\n'
            '    $env:SPOTIPY_CLIENT_SECRET="..."\n'
        )
    return value


def create_spotify_client() -> spotipy.Spotify:
    _require_env("SPOTIPY_CLIENT_ID")
    _require_env("SPOTIPY_CLIENT_SECRET")

    auth_manager = SpotifyClientCredentials()
    return spotipy.Spotify(
        auth_manager=auth_manager,
        requests_timeout=20,
        retries=6,
        status_forcelist=(429, 500, 502, 503, 504),
        backoff_factor=0.4,
    )


def safe_spotify_call(fn: Callable[[], T], *, max_retries: int = 6) -> T:
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return fn()
        except SpotifyException as e:
            last_exc = e
            if e.http_status == 429:
                retry_after = 2
                try:
                    retry_after = int((e.headers or {}).get("Retry-After") or retry_after)
                except Exception:
                    retry_after = 2
                time.sleep(retry_after + 0.5)
                continue

            if e.http_status in (500, 502, 503, 504):
                time.sleep(min(8.0, 0.6 * (2**attempt)))
                continue
            raise
        except Exception as e:
            last_exc = e
            time.sleep(min(8.0, 0.6 * (2**attempt)))
            continue

    assert last_exc is not None
    raise last_exc


def iter_search_artists(
    sp: spotipy.Spotify,
    *,
    genre_query: str,
    limit_total: int,
    market: str = "TR",
    page_size: int = 10,
    sleep_s: float = 0.1,
) -> Iterable[Dict[str, Any]]:
    # Use the raw genre query string; Spotify search now only allows
    # very small page sizes (limit 0–10), so we page in chunks of <=10.
    q = genre_query
    offset = 0

    while offset < limit_total:
        # Spotify search currently enforces limit in [1, 10].
        remaining = max(1, limit_total - offset)
        limit = max(1, min(page_size, remaining, 10))
        resp = safe_spotify_call(lambda: sp.search(q=q, type="artist", limit=limit, offset=offset, market=market))
        items = (resp or {}).get("artists", {}).get("items", []) or []
        if not items:
            return

        for a in items:
            yield a

        if len(items) < limit:
            return

        offset += limit
        if sleep_s:
            time.sleep(sleep_s)


def get_artist_debut_year(
    sp: spotipy.Spotify,
    artist_id: str,
    *,
    country: str = "TR",
    max_items: int = 200,
    page_size: int = 10,
    sleep_s: float = 0.1,
) -> Optional[int]:
    years: List[int] = []
    offset = 0

    while offset < max_items:
        limit = min(page_size, max_items - offset)
        resp = safe_spotify_call(
            lambda: sp.artist_albums(
                artist_id,
                album_type="album,single",
                country=country,
                limit=limit,
                offset=offset,
            )
        )
        items = (resp or {}).get("items", []) or []
        if not items:
            break

        for alb in items:
            release_date = alb.get("release_date")
            precision = alb.get("release_date_precision")
            if not release_date:
                continue

            try:
                if precision == "year":
                    y = int(release_date)
                else:
                    y = int(str(release_date).split("-")[0])
                years.append(y)
            except Exception:
                continue

        if len(items) < limit:
            break

        offset += limit
        if sleep_s:
            time.sleep(sleep_s)

    if not years:
        return None
    return min(years)


def followers_total(artist: Dict[str, Any]) -> int:
    try:
        return int(((artist.get("followers") or {}).get("total")) or 0)
    except Exception:
        return 0


def normalize_artist(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        "genres": a.get("genres", []) or [],
        "followers": a.get("followers") or {"total": 0},
        "debut": None,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build dataset of top Turkish artists from Spotify.")
    p.add_argument("--per-genre", type=int, default=200, help="Max artists to fetch per genre query (default: 200)")
    p.add_argument("--top", type=int, default=500, help="Keep top N artists by followers (default: 500)")
    p.add_argument("--output", type=str, default="artists_raw.json", help="Output JSON file (default: artists_raw.json)")
    p.add_argument("--market", type=str, default="TR", help="Market for search results (default: TR)")
    p.add_argument("--country", type=str, default="TR", help="Country for album release dates (default: TR)")
    p.add_argument("--no-debut", action="store_true", help="Skip debut year enrichment (faster)")
    p.add_argument(
        "--genres",
        type=str,
        default="",
        help='Optional comma-separated genre queries (overrides defaults). Example: "turkish pop,turkish rap"',
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    sp = create_spotify_client()

    genre_queries = GENRE_QUERIES_DEFAULT
    if args.genres.strip():
        genre_queries = [g.strip() for g in args.genres.split(",") if g.strip()]
        if not genre_queries:
            raise SystemExit("No valid genres provided via --genres.")

    artists_by_id: Dict[str, Dict[str, Any]] = {}

    for g in genre_queries:
        print(f"Searching: {g}")
        found = 0
        for raw in iter_search_artists(sp, genre_query=g, limit_total=args.per_genre, market=args.market):
            found += 1
            aid = raw.get("id")
            if not aid:
                continue

            if aid not in artists_by_id:
                artists_by_id[aid] = normalize_artist(raw)

        print(f"  fetched {found} results; unique so far: {len(artists_by_id)}")

    print(f"\nCollected {len(artists_by_id)} unique artists (before sorting).")

    sorted_artists = sorted(artists_by_id.values(), key=followers_total, reverse=True)
    top_artists = sorted_artists[: max(1, int(args.top))]

    if not args.no_debut:
        print(f"\nEnriching debut year for top {len(top_artists)} (may take a while)...")
        for idx, a in enumerate(top_artists, start=1):
            aid = a["id"]
            a["debut"] = get_artist_debut_year(sp, aid, country=args.country)
            if idx % 25 == 0:
                print(f"  debut enriched: {idx}/{len(top_artists)}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(top_artists, f, ensure_ascii=False, indent=2)

    print(f"\nTotal unique artists collected: {len(artists_by_id)}")
    print(f"Saved top {len(top_artists)} to: {args.output}")


if __name__ == "__main__":
    main()

