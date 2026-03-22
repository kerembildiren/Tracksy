"""
Süper Lig CSV'lerinden tüm FB–GS–BJK–TS derbilerini okuyup bundled/derbies.json üretir.

Çalıştır (HarmanGames kökünden veya bu klasörden):
  python build_derby_bundle.py

SUPERLIG_DATA ortam değişkeni ile veri kökü (varsayılan: ../superlig_data).
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import build_derby_index, load_match_truth  # noqa: E402

DEFAULT_DATA = os.path.join(ROOT, "..", "superlig_data")
OUT_PATH = os.path.join(ROOT, "bundled", "derbies.json")


def main() -> None:
    data_root = os.path.abspath(os.environ.get("SUPERLIG_DATA", DEFAULT_DATA))
    idx = build_derby_index(data_root)
    matches: list = []
    for pick in idx:
        t = load_match_truth(data_root, pick["season_key"], pick["match_id"])
        if t.get("home_team"):
            matches.append(t)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    rel = os.path.relpath(data_root, ROOT).replace("\\", "/")
    doc = {
        "version": 1,
        "description": "FB–GS–BJK–TS Süper Lig derbileri; oyun sunucusu bu dosyayı okur.",
        "built_from": rel,
        "match_count": len(matches),
        "matches": matches,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(matches)} matches -> {OUT_PATH}")


if __name__ == "__main__":
    main()
