"""
List player_ids that share the same search-normalized display name (fold_for_search).
Run from repo: python SportsGuesser/DataCollection/football/report_duplicate_player_names.py
SUPERLIG_DATA env overrides the data root (default: superlig_data next to this file).
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
GRID = os.path.join(ROOT, "grid_game")
if GRID not in sys.path:
    sys.path.insert(0, GRID)

from player_index import load_or_build_index  # noqa: E402
from search_util import fold_for_search  # noqa: E402


def main() -> None:
    data_root = os.path.abspath(os.environ.get("SUPERLIG_DATA", os.path.join(ROOT, "superlig_data")))
    players, _ = load_or_build_index(data_root)
    by_fold: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for pid, r in players.items():
        name = (r.name or r.short_name or "").strip()
        if not name:
            continue
        by_fold[fold_for_search(name)].append((pid, name))

    dups = [(k, v) for k, v in by_fold.items() if len(v) > 1]
    dups.sort(key=lambda x: (-len(x[1]), x[0]))

    print(f"Data root: {data_root}")
    print(f"Total players with a name: {sum(len(v) for v in by_fold.values())}")
    print(f"Unique folded names: {len(by_fold)}")
    print(f"Folded names with more than one player_id: {len(dups)}\n")

    for fold_key, entries in dups[:200]:
        print(f"fold={fold_key!r} ({len(entries)} ids)")
        for pid, display in sorted(entries, key=lambda t: t[0]):
            print(f"  {pid}\t{display}")
        print()

    if len(dups) > 200:
        print(f"... and {len(dups) - 200} more groups (truncated)")


if __name__ == "__main__":
    main()
