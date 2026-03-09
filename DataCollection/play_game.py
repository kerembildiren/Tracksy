"""
Turkish Singer Guess - Interactive Test Game
Run with: python play_game.py
"""

import json
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum


# ============================================================
# Models
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


# ============================================================
# Services
# ============================================================

class ArtistDataService:
    def __init__(self):
        self.artists: list[Artist] = []
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
        
        self.artists_by_name = {a.name.lower(): a for a in self.artists}


class DailyArtistService:
    EPOCH_DATE = datetime(2025, 1, 1)
    
    def __init__(self, data_service: ArtistDataService):
        self.data_service = data_service
    
    def get_todays_artist(self) -> Optional[Artist]:
        artists = self.data_service.artists
        if not artists:
            return None
        days_since_epoch = (datetime.now().date() - self.EPOCH_DATE.date()).days
        seed = abs(days_since_epoch)
        hash_val = (seed * 6364136223846793005 + 1442695040888963407) % (2**64)
        index = hash_val % len(artists)
        return artists[index]


class SearchService:
    TURKISH_MAP = {
        'i': 'i', 'I': 'i', 'i': 'i', 'I': 'i',
        'o': 'o', 'O': 'o', 'o': 'o', 'O': 'o',
        'u': 'u', 'U': 'u', 'u': 'u', 'U': 'u',
        's': 's', 'S': 's', 's': 's', 'S': 's',
        'c': 'c', 'C': 'c', 'c': 'c', 'C': 'c',
        'g': 'g', 'G': 'g', 'g': 'g', 'G': 'g',
    }
    
    def __init__(self, data_service: ArtistDataService):
        self.data_service = data_service
    
    def search(self, query: str, limit: int = 5) -> list[Artist]:
        query = query.strip().lower()
        if not query:
            return []
        
        results = []
        for artist in self.data_service.artists:
            if query in artist.name.lower():
                results.append(artist)
        
        # Sort: exact match first, then prefix, then contains
        def sort_key(a: Artist):
            name = a.name.lower()
            if name == query:
                return (0, a.popularity)
            if name.startswith(query):
                return (1, a.popularity)
            return (2, a.popularity)
        
        results.sort(key=sort_key)
        return results[:limit]
    
    def find_exact(self, name: str) -> Optional[Artist]:
        return self.data_service.artists_by_name.get(name.lower())


class HintEngine:
    DEBUT_CLOSE = 3
    LISTENERS_CLOSE = 0.20
    
    def compare(self, guessed: Artist, correct: Artist) -> dict:
        if guessed.id == correct.id:
            return {
                'debut_year': HintResult.CORRECT,
                'group_size': HintResult.CORRECT,
                'gender': HintResult.CORRECT,
                'genre': HintResult.CORRECT,
                'nationality': HintResult.CORRECT,
                'monthly_listeners': HintResult.CORRECT,
            }
        
        return {
            'debut_year': self._compare_numeric(guessed.debut_year, correct.debut_year, self.DEBUT_CLOSE, is_percentage=False),
            'group_size': self._compare_exact(guessed.group_size, correct.group_size),
            'gender': self._compare_exact(guessed.gender, correct.gender),
            'genre': self._compare_exact_ci(guessed.genre, correct.genre),
            'nationality': self._compare_exact_ci(guessed.nationality, correct.nationality),
            'monthly_listeners': self._compare_numeric(guessed.monthly_listeners, correct.monthly_listeners, self.LISTENERS_CLOSE, is_percentage=True),
        }
    
    def _compare_numeric(self, guessed, correct, threshold, is_percentage: bool) -> HintResult:
        if guessed is None or correct is None:
            return HintResult.UNKNOWN
        if guessed == correct:
            return HintResult.CORRECT
        
        if is_percentage:
            diff = abs(guessed - correct) / max(correct, 1)
        else:
            diff = abs(guessed - correct)
        
        is_close = diff <= threshold
        direction_higher = correct > guessed
        
        if is_close:
            return HintResult.CLOSE_HIGHER if direction_higher else HintResult.CLOSE_LOWER
        return HintResult.HIGHER if direction_higher else HintResult.LOWER
    
    def _compare_exact(self, guessed, correct) -> HintResult:
        if guessed is None or correct is None:
            return HintResult.UNKNOWN
        return HintResult.CORRECT if guessed == correct else HintResult.INCORRECT
    
    def _compare_exact_ci(self, guessed, correct) -> HintResult:
        if guessed is None or correct is None:
            return HintResult.UNKNOWN
        return HintResult.CORRECT if guessed.lower() == correct.lower() else HintResult.INCORRECT


# ============================================================
# Display Helpers
# ============================================================

def hint_symbol(result: HintResult) -> str:
    """Returns a visual symbol for the hint result"""
    symbols = {
        HintResult.CORRECT: "[OK]",
        HintResult.INCORRECT: "[X]",
        HintResult.HIGHER: "[^]",      # correct is higher
        HintResult.LOWER: "[v]",       # correct is lower
        HintResult.CLOSE_HIGHER: "[~^]",  # close, correct is higher
        HintResult.CLOSE_LOWER: "[~v]",   # close, correct is lower
        HintResult.UNKNOWN: "[?]",
    }
    return symbols.get(result, "[?]")


def format_value(value, unknown_text="?") -> str:
    """Format a value for display"""
    if value is None:
        return unknown_text
    if isinstance(value, int) and value > 1000:
        if value >= 1_000_000:
            return f"{value/1_000_000:.1f}M"
        return f"{value/1_000:.0f}K"
    return str(value)


def print_header():
    print("\n" + "=" * 70)
    print("          TURKISH SINGER GUESS - Test Mode")
    print("=" * 70)


def print_artist_info(artist: Artist, label: str = "Artist"):
    """Print artist details in a formatted way"""
    print(f"\n{label}: {artist.name}")
    print(f"  Debut Year:        {format_value(artist.debut_year)}")
    print(f"  Group Size:        {format_value(artist.group_size)}")
    print(f"  Gender:            {format_value(artist.gender)}")
    print(f"  Genre:             {format_value(artist.genre)}")
    print(f"  Nationality:       {format_value(artist.nationality)}")
    print(f"  Monthly Listeners: {format_value(artist.monthly_listeners)}")


def print_guess_result(guessed: Artist, hints: dict, guess_num: int):
    """Print the result of a guess with hints"""
    print(f"\n--- Guess #{guess_num}: {guessed.name} ---")
    print(f"  {'Attribute':<20} {'Your Guess':<15} {'Hint':<8}")
    print(f"  {'-'*20} {'-'*15} {'-'*8}")
    print(f"  {'Debut Year':<20} {format_value(guessed.debut_year):<15} {hint_symbol(hints['debut_year'])}")
    print(f"  {'Group Size':<20} {format_value(guessed.group_size):<15} {hint_symbol(hints['group_size'])}")
    print(f"  {'Gender':<20} {format_value(guessed.gender):<15} {hint_symbol(hints['gender'])}")
    print(f"  {'Genre':<20} {format_value(guessed.genre):<15} {hint_symbol(hints['genre'])}")
    print(f"  {'Nationality':<20} {format_value(guessed.nationality):<15} {hint_symbol(hints['nationality'])}")
    print(f"  {'Monthly Listeners':<20} {format_value(guessed.monthly_listeners):<15} {hint_symbol(hints['monthly_listeners'])}")


def print_hint_legend():
    print("\nHint Legend:")
    print("  [OK]  = Correct match")
    print("  [X]   = Wrong")
    print("  [^]   = Correct answer is HIGHER")
    print("  [v]   = Correct answer is LOWER")
    print("  [~^]  = Close! Correct is slightly higher")
    print("  [~v]  = Close! Correct is slightly lower")
    print("  [?]   = Unknown (data not available)")


# ============================================================
# Main Game Loop
# ============================================================

def main():
    # Load data
    filepath = os.path.join(os.path.dirname(__file__), 'output', 'artists_raw.json')
    data_service = ArtistDataService()
    data_service.load_artists(filepath)
    
    daily_service = DailyArtistService(data_service)
    search_service = SearchService(data_service)
    hint_engine = HintEngine()
    
    # Get today's artist
    correct_artist = daily_service.get_todays_artist()
    if not correct_artist:
        print("Error: Could not load artist data")
        return
    
    print_header()
    
    # Show correct answer (TEST MODE)
    print("\n[TEST MODE] The correct answer is shown below:")
    print_artist_info(correct_artist, "SECRET ANSWER")
    
    print_hint_legend()
    
    print("\n" + "-" * 70)
    print("You have 10 guesses. Type an artist name to guess.")
    print("Type 'search <query>' to search for artists.")
    print("Type 'quit' to exit.")
    print("-" * 70)
    
    max_guesses = 10
    guesses_made = 0
    guessed_ids = set()
    
    while guesses_made < max_guesses:
        remaining = max_guesses - guesses_made
        print(f"\n[{remaining} guesses remaining]")
        
        try:
            user_input = input("Your guess: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGame ended.")
            return
        
        if not user_input:
            continue
        
        # Handle commands
        if user_input.lower() == 'quit':
            print(f"\nYou quit. The answer was: {correct_artist.name}")
            return
        
        if user_input.lower().startswith('search '):
            query = user_input[7:].strip()
            results = search_service.search(query, limit=8)
            if results:
                print(f"\nSearch results for '{query}':")
                for i, artist in enumerate(results, 1):
                    already = "(already guessed)" if artist.id in guessed_ids else ""
                    print(f"  {i}. {artist.name} {already}")
            else:
                print(f"No artists found matching '{query}'")
            continue
        
        # Try to find the artist
        guessed_artist = search_service.find_exact(user_input)
        
        if not guessed_artist:
            # Try search and suggest
            results = search_service.search(user_input, limit=5)
            if results:
                print(f"\nArtist '{user_input}' not found exactly. Did you mean:")
                for i, artist in enumerate(results, 1):
                    print(f"  {i}. {artist.name}")
                print("Please type the exact name.")
            else:
                print(f"\nNo artist found matching '{user_input}'. Try 'search <query>'")
            continue
        
        # Check if already guessed
        if guessed_artist.id in guessed_ids:
            print(f"\nYou already guessed {guessed_artist.name}! Try someone else.")
            continue
        
        # Make the guess
        guesses_made += 1
        guessed_ids.add(guessed_artist.id)
        
        hints = hint_engine.compare(guessed_artist, correct_artist)
        print_guess_result(guessed_artist, hints, guesses_made)
        
        # Check for win
        if guessed_artist.id == correct_artist.id:
            print("\n" + "=" * 70)
            print(f"  CONGRATULATIONS! You found the artist in {guesses_made} guess(es)!")
            print("=" * 70)
            return
    
    # Out of guesses
    print("\n" + "=" * 70)
    print(f"  GAME OVER! You ran out of guesses.")
    print(f"  The correct answer was: {correct_artist.name}")
    print("=" * 70)


if __name__ == "__main__":
    main()
