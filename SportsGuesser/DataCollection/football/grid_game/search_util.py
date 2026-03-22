"""
Oyuncu adı araması: Türkçe İ/i/ı ve kısmi eşleşme.
"""

import re


def fold_simple(s: str) -> str:
    if not s:
        return ""
    s = s.replace("İ", "i").replace("I", "ı")
    return s.casefold()


def matches_name_query(name: str, query: str) -> bool:
    if not name:
        return False
    q = (query or "").strip()
    if not q:
        return True
    n = fold_simple(name)
    qf = fold_simple(q)
    if not qf:
        return True
    if qf in n:
        return True
    return all(p in n for p in qf.split() if p)


def best_match_score(name: str, query: str) -> int:
    """Sıralama: daha yüksek = daha iyi eşleşme."""
    qf = fold_simple(query.strip())
    nf = fold_simple(name)
    if not qf:
        return 0
    if nf == qf:
        return 1000 + len(name)
    if nf.startswith(qf):
        return 800 + len(name)
    if qf in nf:
        return 600
    parts = [p for p in qf.split() if p]
    if parts and all(p in nf for p in parts):
        return 400
    return 0
