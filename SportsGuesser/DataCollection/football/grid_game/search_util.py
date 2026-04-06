"""
Oyuncu adı araması: Türkçe İ/i/ı/I, aksanlar (ê, é, ü, ş, …) ve kısmi eşleşme.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional


def fold_for_search(s: str) -> str:
    """
    Tek tip anahtar: aksanları kaldırır, Türkçe i varyantlarını 'i' yapar, boşlukları sadeleştirir.
    Böylece "Ali Güneş", "alı gunes", "ALI GUNES" aynı kovaya düşer.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Dotless i (NFKD sonrası da kalabilir)
    s = s.replace("ı", "i")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fold_simple(s: str) -> str:
    """Geriye dönük uyumluluk; yeni kod fold_for_search kullanmalı."""
    return fold_for_search(s)


def matches_name_query(name: str, query: str) -> bool:
    if not name:
        return False
    q = (query or "").strip()
    if not q:
        return True
    n = fold_for_search(name)
    qf = fold_for_search(q)
    if not qf:
        return True
    if qf in n:
        return True
    return all(p in n for p in qf.split() if p)


def best_match_score(name: str, query: str) -> int:
    """Sıralama: daha yüksek = daha iyi eşleşme."""
    qf = fold_for_search(query.strip())
    nf = fold_for_search(name)
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


def format_suggestion_list(
    rows_sorted: List[tuple],
    *,
    limit: int = 14,
    nationality_for: Callable[[int], Optional[str]],
    name_idx: int = 2,
    pid_idx: int = 3,
) -> List[Dict[str, object]]:
    """
    rows_sorted: (..., display_name, player_id, ...) — tüm eşleşmeler, en iyi önce sıralı.
    Aynı görünen isim birden fazla oyuncuda varsa etikete milliyet veya player_id eklenir
    (aynı isim iki kez görünmez; farklı oyuncular korunur).
    """
    by_name: dict[str, list[int]] = defaultdict(list)
    for row in rows_sorted:
        name = row[name_idx]
        pid = row[pid_idx]
        by_name[name].append(pid)
    for k in by_name:
        by_name[k] = list(dict.fromkeys(by_name[k]))

    def display_label(name: str, pid: int) -> str:
        pids = by_name[name]
        if len(pids) <= 1:
            return name
        my_nat = nationality_for(pid)
        nats = [nationality_for(p) for p in pids]
        cnt = Counter(n for n in nats if n)
        if my_nat and cnt.get(my_nat, 0) == 1:
            return f"{name} ({my_nat})"
        return f"{name} ({pid})"

    out: List[Dict[str, object]] = []
    for row in rows_sorted:
        if len(out) >= limit:
            break
        name = row[name_idx]
        pid = row[pid_idx]
        out.append({"id": pid, "name": display_label(name, pid)})
    return out
