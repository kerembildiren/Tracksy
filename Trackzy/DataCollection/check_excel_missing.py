"""Check artists_raw.xlsx for missing data per artist."""
import openpyxl
import os

# Critical = should usually be filled. Optional = Followers/Last.fm often empty in source.
CRITICAL_FIELDS = ["ID", "Name", "Gender", "Genre(s)", "Nationality", "Debut", "Group size"]
OPTIONAL_FIELDS = ["Followers", "Popularity", "Last.fm listeners", "Last.fm play count"]
ALL_FIELDS = CRITICAL_FIELDS + OPTIONAL_FIELDS

path = os.path.join(os.path.dirname(__file__), "output", "artists_raw.xlsx")
wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
ws = wb["Artists"]
rows = list(ws.iter_rows(values_only=True))
wb.close()

if not rows:
    print("Sheet is empty")
    exit()

header = [str(h).strip() if h is not None else "" for h in rows[0]]
cols = {h: i for i, h in enumerate(header) if h}


def empty(v):
    if v is None:
        return True
    s = str(v).strip()
    return s == "" or s.lower() in ("none", "n/a", "-")


critical_missing = []   # (row, artist_label, list of critical fields)
optional_only = []     # (row, artist_label, list of optional fields) – for info
empty_rows = []        # row indices with no ID and no Name

for row_idx, row in enumerate(rows[1:], 2):
    name = row[cols["Name"]] if "Name" in cols and cols["Name"] < len(row) else ""
    name = str(name).strip() if name is not None else ""
    id_val = row[cols["ID"]] if "ID" in cols and cols["ID"] < len(row) else ""
    id_val = str(id_val).strip() if id_val is not None else ""
    label = name or id_val or ("Row " + str(row_idx))

    missing_crit = [f for f in CRITICAL_FIELDS if f in cols and empty(row[cols[f]] if cols[f] < len(row) else None)]
    missing_opt = [f for f in OPTIONAL_FIELDS if f in cols and empty(row[cols[f]] if cols[f] < len(row) else None)]

    if not name and not id_val:
        empty_rows.append(row_idx)
        continue
    if missing_crit:
        critical_missing.append((row_idx, label, missing_crit))
    elif missing_opt:
        optional_only.append((row_idx, label, missing_opt))

print("=" * 60)
print("1. CRITICAL MISSING (ID, Name, Gender, Genre(s), Nationality, Debut, Group size)")
print("=" * 60)
if not critical_missing:
    print("None. All artists with a name/ID have critical fields filled.")
else:
    for row_idx, label, missing in critical_missing:
        print("Row {} | {}  -->  Missing: {}".format(row_idx, label, ", ".join(missing)))
print()

print("=" * 60)
print("2. EMPTY ROWS (no ID and no Name – safe to delete)")
print("=" * 60)
if not empty_rows:
    print("None.")
else:
    print("Rows: " + ", ".join(str(r) for r in empty_rows))
    print("(Total: {} empty rows)".format(len(empty_rows)))
print()

print("=" * 60)
print("3. OPTIONAL MISSING (only Followers / Popularity / Last.fm – often empty in source)")
print("=" * 60)
print("Followers is empty for most artists (same as original JSON). Only listing artists missing something besides Followers:")
other_opt = [(r, l, [x for x in m if x != "Followers"]) for r, l, m in optional_only if any(x != "Followers" for x in m)]
if not other_opt:
    print("None notable.")
else:
    for row_idx, label, missing in other_opt:
        if missing:
            print("Row {} | {}  -->  Missing: {}".format(row_idx, label, ", ".join(missing)))
print()
print("Summary: {} with critical missing, {} empty rows, {} artists only missing optional (e.g. Followers).".format(
    len(critical_missing), len(empty_rows), len(optional_only)))
