import json

# Load the data
with open('output/artists_raw.json', 'r', encoding='utf-8') as f:
    artists = json.load(f)

# Names to delete (lowercase for comparison)
delete_names = [
    '13 killoki', 'swirf', 'aisu', 'eray067', 'elmusto', 'modd', 'amo988', 'kuty', 
    'tai', 'marss', 'fredd', 'turkodiroma', 'yirmi7', 'rufflws', 'lotusx', 
    'rana türkyılmaz', 'ohash', 'goko!', 'glam', 'tekir', 'çağla', 'doğu swag', 
    'metth', 'kelanei', 'kavak', 'rash', 'kirli', 'pois', 'dethron', 'agoni', 
    'albadeep*', 'ceg06', 'dj sivo', 'zaaf', 'fundyy', 'kava', 'agab', 'aslar', 
    'muerte beatz', 'anatolian psych rock lab', 'oktxy', 'rabona', 'nigar muharrem', 
    'uz4y', 'bke', 'narkoz ex', 'seko', 'harim', 'lrdzdx', 'efo', 'turcyy', 
    'arman aydin', 'palta', 'luffex', 'zeze', 'marsista', 'zedi̇', 'zedİ',
    'yıldırım elmas', 'dj.young.mes', 'rast', 'jeyjey', 'akca', 'vinyl obscura', 
    'ogiboyz', 'karaf', 'ferzanbeats', '4ras inc.', 'busa', 'rap angels', 'koc', 
    'melih', 'giz', 'lessio', 'ali chapo', 'enes güneş', 'hydraxd', 'nesthewest', 
    'laçin', 'bugy', 'aerro', 'still 24', 'turac berkay', 'bero257', 'cesiminho', 
    'aspi', 'zapox', 'anatolian rock echoes', 'sva', 'mesth', 'raperin', 'batuzane', 
    'exre', 'anatolian rock cover türkiye', 'hopera', 'boykot', 'anadolu rock reborn', 
    'kenshi nett', 'yusuflex', 'psychedelic rock cover', 'bakan', 'frozz', 'yasins', 
    'mahmut erbek', 'hayati', 'rapnos', 'beratsh', 'ofy', 'anatolian rock express', 
    'büken', 'alperonly', 'rockiye', 'dengesizKedi', 'dengesızkedi', 'wtfrank', 
    'mavzer tabancas', 'dila bahar', 'funktakl'
]

delete_names_lower = [n.lower() for n in delete_names]

# Filter out artists to delete
original_count = len(artists)
artists = [a for a in artists if a.get('name', '').lower() not in delete_names_lower]
deleted_count = original_count - len(artists)

# Update remaining null nationality artists to Turkey
updated_count = 0
for artist in artists:
    if artist.get('nationality') is None:
        artist['nationality'] = 'Turkey'
        updated_count += 1

# Save
with open('output/artists_raw.json', 'w', encoding='utf-8') as f:
    json.dump(artists, f, indent=2, ensure_ascii=False)

print(f'Deleted: {deleted_count} artists')
print(f'Updated null nationality to Turkey: {updated_count} artists')
print(f'Remaining artists: {len(artists)}')
