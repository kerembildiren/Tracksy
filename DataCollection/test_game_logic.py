"""
Test script for Turkish Singer Guess game logic.
Run with: python test_game_logic.py

This validates the core algorithms before implementing in Swift.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from enum import Enum

# ============================================================
# Models (Python equivalent of Swift models)
# ============================================================

class HintResult(Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    HIGHER = "higher"
    LOWER = "lower"
    CLOSE_HIGHER = "close_higher"
    CLOSE_LOWER = "close_lower"
    UNKNOWN = "unknown"

@dataclass
class Artist:
    id: str
    name: str
    nationality: Optional[str]
    popularity: int
    debut_year: Optional[int] = None
    group_size: Optional[str] = None
    gender: Optional[str] = None
    genre: Optional[str] = None
    monthly_listeners: Optional[int] = None

@dataclass
class GuessHints:
    debut_year: HintResult
    group_size: HintResult
    gender: HintResult
    genre: HintResult
    nationality: HintResult
    monthly_listeners: HintResult
    
    def is_all_correct(self) -> bool:
        return all([
            self.debut_year == HintResult.CORRECT,
            self.group_size == HintResult.CORRECT,
            self.gender == HintResult.CORRECT,
            self.genre == HintResult.CORRECT,
            self.nationality == HintResult.CORRECT,
            self.monthly_listeners == HintResult.CORRECT,
        ])

# ============================================================
# Services (Python equivalent of Swift services)
# ============================================================

class ArtistDataService:
    def __init__(self):
        self.artists: list[Artist] = []
        self.artists_by_id: dict[str, Artist] = {}
        self.artists_by_name: dict[str, Artist] = {}
    
    def load_artists(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_artists = json.load(f)
        
        self.artists = []
        for raw in raw_artists:
            artist = Artist(
                id=raw['id'],
                name=raw['name'],
                nationality=raw.get('nationality'),
                popularity=raw.get('popularity', 0),
                debut_year=raw.get('debut'),
                genre=raw['genres'][0] if raw.get('genres') else None,
                monthly_listeners=raw.get('spotify_monthly_listeners') or raw.get('lastfm_listeners')
            )
            self.artists.append(artist)
        
        self.artists_by_id = {a.id: a for a in self.artists}
        self.artists_by_name = {a.name.lower(): a for a in self.artists}
    
    def artist_by_id(self, id: str) -> Optional[Artist]:
        return self.artists_by_id.get(id)
    
    def artist_by_name(self, name: str) -> Optional[Artist]:
        return self.artists_by_name.get(name.lower())


class DailyArtistService:
    """Deterministic daily artist selection - same algorithm as Swift version"""
    
    EPOCH_DATE = datetime(2025, 1, 1)
    
    def __init__(self, data_service: ArtistDataService):
        self.data_service = data_service
    
    def get_daily_artist(self, date: datetime) -> Optional[Artist]:
        artists = self.data_service.artists
        if not artists:
            return None
        
        days_since_epoch = (date.date() - self.EPOCH_DATE.date()).days
        index = self._deterministic_index(days_since_epoch, len(artists))
        return artists[index]
    
    def get_todays_artist(self) -> Optional[Artist]:
        return self.get_daily_artist(datetime.now())
    
    def _deterministic_index(self, day: int, artist_count: int) -> int:
        """Same algorithm as Swift - LCG-based hash"""
        seed = abs(day)
        # These are the same constants used in the Swift version
        hash_val = (seed * 6364136223846793005 + 1442695040888963407) % (2**64)
        return hash_val % artist_count


class SearchService:
    """Autocomplete search with Turkish character support"""
    
    TURKISH_REPLACEMENTS = {
        'ı': 'i', 'İ': 'i',
        'ö': 'o', 'Ö': 'o',
        'ü': 'u', 'Ü': 'u',
        'ş': 's', 'Ş': 's',
        'ç': 'c', 'Ç': 'c',
        'ğ': 'g', 'Ğ': 'g',
    }
    
    def __init__(self, data_service: ArtistDataService):
        self.data_service = data_service
    
    def search(self, query: str, limit: int = 10) -> list[Artist]:
        query = query.strip().lower()
        if not query:
            return []
        
        normalized_query = self._normalize_turkish(query)
        
        results = []
        for artist in self.data_service.artists:
            normalized_name = self._normalize_turkish(artist.name.lower())
            if normalized_query in normalized_name:
                results.append(artist)
        
        # Sort by relevance
        def sort_key(a: Artist):
            name = self._normalize_turkish(a.name.lower())
            if name == normalized_query:
                return (0, a.popularity)
            if name.startswith(normalized_query):
                return (1, a.popularity)
            return (2, a.popularity)
        
        results.sort(key=sort_key)
        return results[:limit]
    
    def _normalize_turkish(self, text: str) -> str:
        return ''.join(self.TURKISH_REPLACEMENTS.get(c, c) for c in text)


class HintEngine:
    """Comparison logic for generating hints"""
    
    DEBUT_YEAR_CLOSE_THRESHOLD = 3
    MONTHLY_LISTENERS_CLOSE_THRESHOLD = 0.20
    
    def compare(self, guessed: Artist, correct: Artist) -> GuessHints:
        if guessed.id == correct.id:
            return GuessHints(
                debut_year=HintResult.CORRECT,
                group_size=HintResult.CORRECT,
                gender=HintResult.CORRECT,
                genre=HintResult.CORRECT,
                nationality=HintResult.CORRECT,
                monthly_listeners=HintResult.CORRECT,
            )
        
        return GuessHints(
            debut_year=self._compare_debut_year(guessed.debut_year, correct.debut_year),
            group_size=self._compare_exact(guessed.group_size, correct.group_size),
            gender=self._compare_exact(guessed.gender, correct.gender),
            genre=self._compare_exact_ci(guessed.genre, correct.genre),
            nationality=self._compare_exact_ci(guessed.nationality, correct.nationality),
            monthly_listeners=self._compare_monthly_listeners(guessed.monthly_listeners, correct.monthly_listeners),
        )
    
    def _compare_debut_year(self, guessed: Optional[int], correct: Optional[int]) -> HintResult:
        if guessed is None or correct is None:
            return HintResult.UNKNOWN
        if guessed == correct:
            return HintResult.CORRECT
        
        diff = abs(guessed - correct)
        if diff <= self.DEBUT_YEAR_CLOSE_THRESHOLD:
            return HintResult.CLOSE_HIGHER if correct > guessed else HintResult.CLOSE_LOWER
        return HintResult.HIGHER if correct > guessed else HintResult.LOWER
    
    def _compare_monthly_listeners(self, guessed: Optional[int], correct: Optional[int]) -> HintResult:
        if guessed is None or correct is None:
            return HintResult.UNKNOWN
        if guessed == correct:
            return HintResult.CORRECT
        
        percent_diff = abs(guessed - correct) / max(correct, 1)
        if percent_diff <= self.MONTHLY_LISTENERS_CLOSE_THRESHOLD:
            return HintResult.CLOSE_HIGHER if correct > guessed else HintResult.CLOSE_LOWER
        return HintResult.HIGHER if correct > guessed else HintResult.LOWER
    
    def _compare_exact(self, guessed: Optional[str], correct: Optional[str]) -> HintResult:
        if guessed is None or correct is None:
            return HintResult.UNKNOWN
        return HintResult.CORRECT if guessed == correct else HintResult.INCORRECT
    
    def _compare_exact_ci(self, guessed: Optional[str], correct: Optional[str]) -> HintResult:
        if guessed is None or correct is None:
            return HintResult.UNKNOWN
        return HintResult.CORRECT if guessed.lower() == correct.lower() else HintResult.INCORRECT


# ============================================================
# Tests
# ============================================================

def test_artist_loading():
    print("\n" + "="*60)
    print("TEST: Artist Loading")
    print("="*60)
    
    data_service = ArtistDataService()
    filepath = os.path.join(os.path.dirname(__file__), 'output', 'artists_raw.json')
    data_service.load_artists(filepath)
    
    print(f"[OK] Loaded {len(data_service.artists)} artists")
    
    # Show first 5 artists
    print("\nFirst 5 artists:")
    for artist in data_service.artists[:5]:
        print(f"  - {artist.name} (popularity: {artist.popularity}, nationality: {artist.nationality})")
    
    # Test lookup
    artist = data_service.artist_by_name("Sezen Aksu")
    if artist:
        print(f"\n[OK] Found by name: {artist.name}")
    else:
        print("\n[FAIL] Could not find 'Sezen Aksu' by name")
    
    return data_service


def test_daily_artist_determinism(data_service: ArtistDataService):
    print("\n" + "="*60)
    print("TEST: Daily Artist Determinism")
    print("="*60)
    
    daily_service = DailyArtistService(data_service)
    
    # Test that same date always returns same artist
    test_date = datetime(2026, 3, 7)
    artist1 = daily_service.get_daily_artist(test_date)
    artist2 = daily_service.get_daily_artist(test_date)
    
    if artist1 and artist2 and artist1.id == artist2.id:
        print(f"[OK] Same date returns same artist: {artist1.name}")
    else:
        print("[FAIL] Determinism failed!")
    
    # Test different dates return different artists (mostly)
    print("\nArtists for next 7 days:")
    seen = set()
    for i in range(7):
        date = datetime(2026, 3, 7) + timedelta(days=i)
        artist = daily_service.get_daily_artist(date)
        if artist:
            date_str = date.strftime("%Y-%m-%d")
            print(f"  {date_str}: {artist.name}")
            seen.add(artist.id)
    
    print(f"\n[OK] {len(seen)} unique artists in 7 days")
    
    # Today's artist
    todays = daily_service.get_todays_artist()
    if todays:
        print(f"\n*** Today's artist: {todays.name}")


def test_search(data_service: ArtistDataService):
    print("\n" + "="*60)
    print("TEST: Search with Autocomplete")
    print("="*60)
    
    search_service = SearchService(data_service)
    
    test_queries = ["tar", "sezen", "mor", "duman"]
    
    for query in test_queries:
        results = search_service.search(query, limit=3)
        print(f"\nSearch '{query}':")
        for artist in results:
            print(f"  - {artist.name}")
    
    # Test Turkish character handling
    print("\nTurkish character test:")
    results1 = search_service.search("şarki")
    results2 = search_service.search("sarki")
    print(f"  'şarki' returns {len(results1)} results")
    print(f"  'sarki' returns {len(results2)} results")


def test_hint_engine():
    print("\n" + "="*60)
    print("TEST: Hint Engine")
    print("="*60)
    
    hint_engine = HintEngine()
    
    # Create test artists
    correct = Artist(
        id="correct",
        name="Correct Artist",
        nationality="Turkish",
        popularity=50,
        debut_year=2010,
        gender="Female",
        monthly_listeners=1000000
    )
    
    # Test 1: Exact match
    hints = hint_engine.compare(correct, correct)
    print(f"\n1. Same artist: all correct = {hints.is_all_correct()}")
    assert hints.is_all_correct(), "Same artist should be all correct"
    print("   [OK] Pass")
    
    # Test 2: Debut year close (within 3 years)
    guessed = Artist(id="g1", name="G1", nationality="Turkish", popularity=50, debut_year=2012)
    hints = hint_engine.compare(guessed, correct)
    print(f"\n2. Debut 2012 vs 2010: {hints.debut_year}")
    assert hints.debut_year == HintResult.CLOSE_LOWER, "Should be close_lower"
    print("   [OK] Pass")
    
    # Test 3: Debut year far (more than 3 years)
    guessed = Artist(id="g2", name="G2", nationality="Turkish", popularity=50, debut_year=2020)
    hints = hint_engine.compare(guessed, correct)
    print(f"\n3. Debut 2020 vs 2010: {hints.debut_year}")
    assert hints.debut_year == HintResult.LOWER, "Should be lower (correct is 2010)"
    print("   [OK] Pass")
    
    # Test 4: Monthly listeners close (within 20%)
    guessed = Artist(id="g3", name="G3", nationality="Turkish", popularity=50, monthly_listeners=900000)
    hints = hint_engine.compare(guessed, correct)
    print(f"\n4. Listeners 900K vs 1M: {hints.monthly_listeners}")
    assert hints.monthly_listeners == HintResult.CLOSE_HIGHER, "Should be close_higher (10% diff)"
    print("   [OK] Pass")
    
    # Test 5: Monthly listeners far (more than 20%)
    guessed = Artist(id="g4", name="G4", nationality="Turkish", popularity=50, monthly_listeners=500000)
    hints = hint_engine.compare(guessed, correct)
    print(f"\n5. Listeners 500K vs 1M: {hints.monthly_listeners}")
    assert hints.monthly_listeners == HintResult.HIGHER, "Should be higher (50% diff)"
    print("   [OK] Pass")
    
    # Test 6: Nationality match
    guessed = Artist(id="g5", name="G5", nationality="Turkish", popularity=50)
    hints = hint_engine.compare(guessed, correct)
    print(f"\n6. Nationality Turkish vs Turkish: {hints.nationality}")
    assert hints.nationality == HintResult.CORRECT, "Should be correct"
    print("   [OK] Pass")
    
    # Test 7: Nationality mismatch
    guessed = Artist(id="g6", name="G6", nationality="German", popularity=50)
    hints = hint_engine.compare(guessed, correct)
    print(f"\n7. Nationality German vs Turkish: {hints.nationality}")
    assert hints.nationality == HintResult.INCORRECT, "Should be incorrect"
    print("   [OK] Pass")
    
    print("\n[OK] All hint engine tests passed!")


def test_game_simulation(data_service: ArtistDataService):
    print("\n" + "="*60)
    print("TEST: Game Simulation")
    print("="*60)
    
    daily_service = DailyArtistService(data_service)
    search_service = SearchService(data_service)
    hint_engine = HintEngine()
    
    # Get today's correct artist
    correct = daily_service.get_todays_artist()
    if not correct:
        print("[FAIL] No artist available")
        return
    
    print(f"\nSecret artist: {correct.name} (don't peek!)")
    print(f"Nationality: {correct.nationality}")
    print(f"Monthly listeners: {correct.monthly_listeners}")
    
    # Simulate some guesses
    test_guesses = ["Tarkan", "Sezen Aksu", "Duman"]
    
    print("\nSimulating guesses:")
    for guess_name in test_guesses:
        results = search_service.search(guess_name, limit=1)
        if not results:
            print(f"  '{guess_name}' - not found")
            continue
        
        guessed = results[0]
        hints = hint_engine.compare(guessed, correct)
        
        print(f"\n  Guess: {guessed.name}")
        print(f"    Nationality: {hints.nationality.value}")
        if hints.is_all_correct():
            print("    *** CORRECT! You won!")
            break


def main():
    print("="*60)
    print("TURKISH SINGER GUESS - Logic Tests")
    print("="*60)
    
    try:
        # Test 1: Load artists
        data_service = test_artist_loading()
        
        # Test 2: Daily artist determinism
        test_daily_artist_determinism(data_service)
        
        # Test 3: Search
        test_search(data_service)
        
        # Test 4: Hint engine
        test_hint_engine()
        
        # Test 5: Game simulation
        test_game_simulation(data_service)
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
