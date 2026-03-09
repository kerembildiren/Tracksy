import musicbrainzngs
import json
import time
import os

# Set up the MusicBrainz client
musicbrainzngs.set_useragent(
    "TurkishArtistDataCollector",
    "1.0",
    "https://github.com/example/turkish-artists"
)

def search_artist_musicbrainz(artist_name):
    """
    Search for an artist on MusicBrainz using the official library.
    """
    try:
        result = musicbrainzngs.search_artists(artist=artist_name, limit=5)
        return result.get('artist-list', [])
    except Exception as e:
        print(f"Error: {type(e).__name__}")
        return None

def get_best_match(artists, original_name):
    """
    Find the best matching artist from search results.
    Prioritizes exact name matches and high scores.
    """
    if not artists:
        return None
    
    original_lower = original_name.lower().strip()
    
    # First try exact match
    for artist in artists:
        if artist.get('name', '').lower().strip() == original_lower:
            return artist
    
    # If no exact match, return highest scored result
    return artists[0] if artists else None

def extract_artist_info(artist_data):
    """
    Extract nationality (area), debut (begin year), group_size (type), and gender from artist data.
    """
    result = {
        'nationality': None,
        'debut': None,
        'group_size': None,
        'gender': None
    }
    
    if not artist_data:
        return result
    
    # Extract area/nationality - prefer country code, then area name
    country = artist_data.get('country')
    if country:
        # Map country codes to full names for common ones
        country_map = {
            'TR': 'Turkey',
            'US': 'United States',
            'GB': 'United Kingdom',
            'DE': 'Germany',
            'FR': 'France',
            'JP': 'Japan',
            'KR': 'South Korea',
            'IT': 'Italy',
            'ES': 'Spain',
            'NL': 'Netherlands',
            'SE': 'Sweden',
            'NO': 'Norway',
            'FI': 'Finland',
            'DK': 'Denmark',
            'RU': 'Russia',
            'BR': 'Brazil',
            'MX': 'Mexico',
            'CA': 'Canada',
            'AU': 'Australia',
            'AZ': 'Azerbaijan',
            'GR': 'Greece',
            'IR': 'Iran',
            'SY': 'Syria',
            'LB': 'Lebanon',
            'EG': 'Egypt',
            'MA': 'Morocco',
            'DZ': 'Algeria',
            'TN': 'Tunisia',
        }
        result['nationality'] = country_map.get(country, country)
    else:
        # Fall back to area name
        area = artist_data.get('area')
        if area:
            result['nationality'] = area.get('name')
    
    # Extract begin date (year only)
    life_span = artist_data.get('life-span')
    if life_span:
        begin = life_span.get('begin')
        if begin:
            # Extract just the year (first 4 characters)
            result['debut'] = begin[:4] if len(begin) >= 4 else begin
    
    # Extract type -> group_size
    artist_type = artist_data.get('type')
    if artist_type:
        if artist_type.lower() == 'person':
            result['group_size'] = 1
        elif artist_type.lower() in ['group', 'orchestra', 'choir']:
            result['group_size'] = 'group'
        elif artist_type.lower() == 'character':
            result['group_size'] = 'character'
        else:
            result['group_size'] = artist_type
    
    # Extract gender (only available for Person type)
    gender = artist_data.get('gender')
    if gender:
        result['gender'] = gender.capitalize()
    elif artist_type and artist_type.lower() in ['group', 'orchestra', 'choir']:
        result['gender'] = 'Mixed'
    
    return result

def update_artists_file(input_file, output_file=None, start_from=0, gender_only=False, start_after_name=None):
    """
    Read artists from JSON file, fetch MusicBrainz data, and update the file.
    If gender_only=True, only fetch data for artists missing gender.
    If start_after_name is set (e.g. "Joker"), only process artists that appear after that name in the list.
    """
    if output_file is None:
        output_file = input_file
    
    # Read the JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        artists = json.load(f)
    
    # Optional: only process artists after a given name (e.g. Joker)
    min_index = 0
    if start_after_name:
        found = None
        for i, a in enumerate(artists):
            if (a.get("name") or "").strip() == start_after_name.strip():
                found = i
        if found is None:
            raise SystemExit(f"Artist '{start_after_name}' not found in JSON.")
        min_index = found + 1
        print(f"Processing only artists after '{start_after_name}' (from index {min_index + 1} to end).\n")
    
    total = len(artists)
    updated_count = 0
    not_found_count = 0
    skipped_count = 0
    
    if gender_only:
        print(f"Gender-only mode: Only fetching gender for artists missing it...")
    
    if start_from > 0:
        print(f"Resuming MusicBrainz data collection from artist {start_from + 1}...")
    elif min_index > 0:
        print(f"Starting MusicBrainz data collection for artists {min_index + 1} to {total}...")
    else:
        print(f"Starting MusicBrainz data collection for {total} artists...")
    print("Rate limited to 1 request per second as per MusicBrainz API guidelines.\n")
    
    for i, artist in enumerate(artists):
        # Skip artists before start_after (e.g. only "below Joker")
        if i < min_index:
            continue
        # Skip already processed artists
        if i < start_from:
            continue
        
        # In gender-only mode, skip artists that already have gender
        if gender_only and artist.get('gender'):
            skipped_count += 1
            continue
        
        name = artist.get('name', '')
        # Handle Unicode characters that might not display in console
        try:
            display_name = name.encode('cp1254', errors='replace').decode('cp1254')
        except:
            display_name = name.encode('ascii', errors='replace').decode('ascii')
        print(f"[{i+1}/{total}] Searching: {display_name}...", end=' ', flush=True)
        
        # Search MusicBrainz
        search_results = search_artist_musicbrainz(name)
        
        if search_results:
            best_match = get_best_match(search_results, name)
            
            if best_match:
                info = extract_artist_info(best_match)
                
                if gender_only:
                    # Only update gender
                    if info['gender']:
                        artist['gender'] = info['gender']
                        updated_count += 1
                        print(f"Found! Gender: {info['gender']}")
                    else:
                        not_found_count += 1
                        print("No gender info")
                else:
                    # Update all fields
                    if info['nationality']:
                        artist['nationality'] = info['nationality']
                    if info['debut']:
                        artist['debut'] = info['debut']
                    if info['group_size']:
                        artist['group_size'] = info['group_size']
                    if info['gender']:
                        artist['gender'] = info['gender']
                    
                    updated_count += 1
                    print(f"Found! Type: {info['group_size']}, Gender: {info['gender']}, Area: {info['nationality']}, Begin: {info['debut']}")
            else:
                not_found_count += 1
                print("No good match found")
        else:
            not_found_count += 1
            print("Not found")
        
        # Rate limiting: 1 request per second (MusicBrainz requirement)
        time.sleep(1.1)
        
        # Save progress every 50 artists
        if (i + 1) % 50 == 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(artists, f, indent=2, ensure_ascii=False)
            print(f"\n--- Progress saved ({i+1}/{total}) ---\n")
    
    # Save final data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(artists, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"Total artists: {total}")
    if gender_only:
        print(f"Skipped (already have gender): {skipped_count}")
    print(f"Updated: {updated_count}")
    print(f"Not found: {not_found_count}")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
MusicBrainz Artist Data Scraper
===============================

Usage:
  python musicbrainz_scraper.py                  # Fetch all data for all artists
  python musicbrainz_scraper.py --gender-only    # Only fetch gender for artists missing it
  python musicbrainz_scraper.py --continue=N     # Resume from artist N (0-indexed)
  python musicbrainz_scraper.py --test           # Test with sample artists
  python musicbrainz_scraper.py --help           # Show this help

Options can be combined:
  python musicbrainz_scraper.py --gender-only --continue=100
  python musicbrainz_scraper.py --start-after Joker   # Only artists below Joker (e.g. playlist-added)
        """)
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Testing MusicBrainz API with sample artists...\n")
        test_artists = ["Tarkan", "Sezen Aksu", "Duman", "mor ve ötesi", "Barış Manço"]
        
        for name in test_artists:
            print(f"Searching: {name}")
            results = search_artist_musicbrainz(name)
            
            if results:
                best = get_best_match(results, name)
                if best:
                    info = extract_artist_info(best)
                    print(f"  Name: {best.get('name')}")
                    print(f"  Type: {best.get('type')} -> group_size: {info['group_size']}")
                    print(f"  Gender: {info['gender']}")
                    print(f"  Area: {info['nationality']}")
                    print(f"  Begin: {info['debut']}")
                    print()
            else:
                print("  Not found\n")
            
            time.sleep(1.1)  # Rate limiting
    else:
        # Run full update
        input_file = os.path.join(os.path.dirname(__file__), 'output', 'artists_raw.json')
        
        # Parse arguments
        start_from = 0
        gender_only = False
        start_after_name = None
        
        args_list = sys.argv[1:]
        idx = 0
        while idx < len(args_list):
            arg = args_list[idx]
            if arg.startswith('--continue='):
                start_from = int(arg.split('=')[1])
            elif arg == '--gender-only':
                gender_only = True
            elif arg.startswith('--start-after='):
                start_after_name = arg.split('=', 1)[1].strip()
            elif arg == '--start-after' and idx + 1 < len(args_list) and not args_list[idx + 1].startswith('--'):
                start_after_name = args_list[idx + 1].strip()
                idx += 1
            idx += 1
        
        update_artists_file(input_file, start_from=start_from, gender_only=gender_only, start_after_name=start_after_name)
