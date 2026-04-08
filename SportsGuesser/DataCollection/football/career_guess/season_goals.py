"""Aggregate Süper Lig goals per (player_id, season) from goals.csv files."""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Dict, Tuple

GoalKey = Tuple[int, str]


def build_season_goals_map(data_root: str) -> Dict[GoalKey, int]:
    """For each season folder with goals.csv, count rows where scorer_id == player."""
    root = os.path.abspath(data_root)
    counts: Dict[GoalKey, int] = defaultdict(int)
    for season in sorted(os.listdir(root)):
        folder = os.path.join(root, season)
        if not os.path.isdir(folder):
            continue
        path = os.path.join(folder, "goals.csv")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "scorer_id" not in reader.fieldnames:
                continue
            for row in reader:
                raw = row.get("scorer_id")
                if not raw or not str(raw).strip():
                    continue
                try:
                    pid = int(raw)
                except (TypeError, ValueError):
                    continue
                if pid > 0:
                    counts[(pid, season)] += 1
    return dict(counts)
