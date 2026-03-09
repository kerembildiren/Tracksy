import json

# Load the data
with open('output/artists_raw.json', 'r', encoding='utf-8') as f:
    artists = json.load(f)

# Names to delete (lowercase for comparison)
delete_names = [
    'metro', 'gringo', '2run', '90 bpm', 'turkish delight', 'ali471', 'cairo', 
    'istanbul trip', 'vagon', 'gri', 'josef', 'pit10', 'samet aka spud', 'ikra', 
    'dr. fuchs', 'rope', 'rıza tamer', 'kres', "k'st", 'salman tin', 'röya', 
    'a-bacchus', 'chiko', 'bar b', 'ankara echoes', 'seco', 'waxy', 
    'geenaro & ghana beats', 'shelby', 'enes', 'nun sultan', 'samet kardeşler', 
    'çinarə məlikzadə', 'oğuz ünal', 'ozi vrd', 'groz', 'anatolia rock house', 
    'chahid', 'turkish ritim house', 'emin asker', 'şerif ali boztepe', 
    'rap futbol', 'isa barak', 'turkish anatolian', 'turkish cover lab',
    'pango', 'elcano'  # Adding a couple more that seem non-Turkish
]

delete_names_lower = [n.lower() for n in delete_names]

# Filter out artists to delete
original_count = len(artists)
artists = [a for a in artists if a.get('name', '').lower() not in delete_names_lower]
deleted_count = original_count - len(artists)

# Update remaining non-Turkey artists to Turkey
updated_count = 0
for artist in artists:
    nat = artist.get('nationality')
    if nat and nat != 'Turkey':
        artist['nationality'] = 'Turkey'
        updated_count += 1

# Save
with open('output/artists_raw.json', 'w', encoding='utf-8') as f:
    json.dump(artists, f, indent=2, ensure_ascii=False)

print(f'Deleted: {deleted_count} artists')
print(f'Updated nationality to Turkey: {updated_count} artists')
print(f'Remaining artists: {len(artists)}')
