"""
TFF.org arşivinden 2011/12 Süper Lig için eksik gol verisini tamamlar.

Kaynak: https://www.tff.org/default.aspx?pageID=1139

Çıktılar (varsayılan: ../superlig_data/archive/11-12_tff/; 11-12 klasörü sadece standart CSV):
  - tff_gol_kralligi.csv     — sezonluk gol sayıları (TFF resmi)
  - tff_match_index.csv      — tüm maçların macId + skor + kulüp id
  - tff_goals_by_match.csv   — maç başına gol (oyuncu + dk) — merge script ile goals.csv

Kullanım:
  pip install requests
  python fetch_tff_1112_supplement.py
  python fetch_tff_1112_supplement.py --skip-matches   # sadece gol krallığı
"""

from __future__ import annotations

import argparse
import csv
import html as html_module
import re
import sys
import time
from pathlib import Path
import requests

ENCODING = "windows-1254"
TFF_ARCHIVE_1112 = "https://www.tff.org/default.aspx?pageID=1139"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_text(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    r.encoding = ENCODING
    return r.text


def parse_gol_kralligi(html: str) -> list[dict]:
    """pageID=1139 üst kısmındaki gol krallığı tablosu (HTML)."""
    rows: list[dict] = []
    # Gerçek HTML: <a ... kisiID=91384">BURAK ...</a></b><br /> ... kulupID=3596">TRABZON...
    # ... lblGolSayisi">33</span>
    cell_re = re.compile(
        r'pageID=30&amp;kisiID=(\d+)"[^>]*>([^<]+)</a></b><br />\s*'
        r'<a[^>]*kulupID=(\d+)"[^>]*>([^<]+)</a>\s*'
        r'<td[^>]*>\s*<b>\s*<span[^>]*>(\d+)</span>',
        re.I | re.S,
    )
    for m in cell_re.finditer(html):
        kisi, name, kulup, club, goals = m.groups()
        rows.append(
            {
                "tff_kisi_id": int(kisi),
                "player_name_tff": name.strip(),
                "club_name_tff": club.strip(),
                "tff_kulup_id": int(kulup),
                "goals_season_tff": int(goals),
            }
        )
    return rows


def parse_mac_ids(html: str) -> list[int]:
    return sorted(set(int(x) for x in re.findall(r"macId=(\d+)", html, flags=re.I)))


def _parse_goal_anchor_text(raw: str) -> tuple[str, int] | None:
    """TFF: 'SOYAD AD...,31.dk (F)' veya 'İSİM  45.dk'"""
    raw = html_module.unescape(raw.strip())
    m = re.search(r"(\d+)\s*\.?\s*dk", raw, re.I)
    if not m:
        return None
    minute = int(m.group(1))
    name = raw[: m.start()].strip().rstrip(",").strip()
    if not name:
        return None
    return name, minute


def parse_match_report(html: str, mac_id: int) -> tuple[list[dict], dict]:
    """
    Maç detayından skor, kulüpler ve golleri çıkarır.
    Maç sayfası: pageId=28 kullanır kulupId= (küçük d); gol linkleri lblGol + kisiId=.
    """
    meta: dict = {"tff_mac_id": mac_id}
    ht = re.search(r'lnkTakim1" href="[^"]*kulupId=(\d+)"', html, re.I)
    at = re.search(r'lnkTakim2" href="[^"]*kulupId=(\d+)"', html, re.I)
    hs = re.search(r"lblTakim1Skor\">(\d+)</span>", html, re.I)
    # Deplasman skoru farklı span id ile gelebiliyor; ikinci MacDetaySayi bloğu
    away_block = html.split("lnkTakim2", 1)[-1] if "lnkTakim2" in html else html
    aws = re.search(
        r'class="MacDetaySayi"[^>]*>\s*<span[^>]*>(\d+)</span>',
        away_block,
        re.I | re.S,
    )
    if ht and at and hs and aws:
        meta["home_kulup_id"] = int(ht.group(1))
        meta["away_kulup_id"] = int(at.group(1))
        meta["home_score"] = int(hs.group(1))
        meta["away_score"] = int(aws.group(1))

    goals_out: list[dict] = []
    # Resmi maç raporu: sadece gol satırlarında lblGol + oyuncu linki
    for gm in re.finditer(
        r'<a(?=[^>]*lblGol)[^>]*kisiId=(\d+)[^>]*>([^<]+)</a>',
        html,
        re.I,
    ):
        parsed = _parse_goal_anchor_text(gm.group(2))
        if not parsed:
            continue
        name, minute = parsed
        goals_out.append(
            {
                "tff_mac_id": mac_id,
                "tff_kisi_id": int(gm.group(1)),
                "scorer_name_tff": name,
                "minute": minute,
            }
        )

    if not goals_out:
        for gm in re.finditer(
            r'<a(?=[^>]*lblGol)[^>]*kisiID=(\d+)[^>]*>([^<]+)</a>',
            html,
            re.I,
        ):
            parsed = _parse_goal_anchor_text(gm.group(2))
            if not parsed:
                continue
            name, minute = parsed
            goals_out.append(
                {
                    "tff_mac_id": mac_id,
                    "tff_kisi_id": int(gm.group(1)),
                    "scorer_name_tff": name,
                    "minute": minute,
                }
            )

    return goals_out, meta


def main() -> None:
    parser = argparse.ArgumentParser(description="TFF 2011/12 gol tamamlayıcı")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "superlig_data"
        / "archive"
        / "11-12_tff",
        help="TFF ara çıktıları (standart 11-12 dışında)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
        help="Maç sayfaları arası saniye",
    )
    parser.add_argument(
        "--skip-matches",
        action="store_true",
        help="Sadece gol krallığı (maç detaylarını indirme)",
    )
    args = parser.parse_args()
    out: Path = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    print(f"İndiriliyor: {TFF_ARCHIVE_1112}")
    html = fetch_text(TFF_ARCHIVE_1112)

    gk = parse_gol_kralligi(html)
    gk_path = out / "tff_gol_kralligi.csv"
    if gk:
        with open(gk_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "tff_kisi_id",
                    "player_name_tff",
                    "club_name_tff",
                    "tff_kulup_id",
                    "goals_season_tff",
                ],
            )
            w.writeheader()
            w.writerows(gk)
        print(f"  [OK] {gk_path}  ({len(gk)} oyuncu)")
    else:
        print(
            "  [WARN] Gol kralligi parse edilemedi (TFF HTML yapisi degismis olabilir).",
            file=sys.stderr,
        )

    if args.skip_matches:
        print("Bitti (--skip-matches).")
        return

    mac_ids = parse_mac_ids(html)
    print(f"  {len(mac_ids)} benzersiz macId bulundu — maç raporları indiriliyor...")

    index_rows: list[dict] = []
    goal_rows: list[dict] = []
    for i, mid in enumerate(mac_ids, 1):
        url = f"https://www.tff.org/Default.aspx?pageId=29&macId={mid}"
        try:
            rep = fetch_text(url)
        except Exception as ex:
            print(f"  [WARN] macId={mid}: {ex}")
            time.sleep(args.delay)
            continue
        goals, meta = parse_match_report(rep, mid)
        index_rows.append(meta)
        for j, g in enumerate(goals, 1):
            goal_rows.append({**g, "goal_order": j})
        if i % 50 == 0:
            print(f"    ... {i}/{len(mac_ids)}")
        time.sleep(args.delay)

    idx_path = out / "tff_match_index.csv"
    if index_rows:
        keys = sorted({k for row in index_rows for k in row.keys()})
        with open(idx_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(index_rows)
        print(f"  [OK] {idx_path}")

    gbm_path = out / "tff_goals_by_match.csv"
    if goal_rows:
        with open(gbm_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "tff_mac_id",
                    "tff_kisi_id",
                    "scorer_name_tff",
                    "minute",
                    "goal_order",
                ],
            )
            w.writeheader()
            w.writerows(goal_rows)
        print(f"  [OK] {gbm_path}  ({len(goal_rows)} gol satiri)")
    else:
        print(
            "  [WARN] Hic gol satiri uretilemedi -- regex guncellemesi gerekebilir.",
            file=sys.stderr,
        )

    print("\nKaynak: https://www.tff.org/default.aspx?pageID=1139")
    print(
        "Not: SofaScore player_id ile eşleştirme için isim/kisiID eşlemesi ayrı yapılmalı; "
        "Alex (TFF kisiID=30091) gol krallığında 14 gol görünür."
    )


if __name__ == "__main__":
    main()
