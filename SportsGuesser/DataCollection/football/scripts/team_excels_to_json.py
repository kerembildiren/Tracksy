"""
Convert Excel files (97-2003 .xls and .xlsx) in TeamExcels folder to JSON.
Also handles files saved as .xls that are actually HTML (e.g. from browser export).
Each workbook becomes one JSON file: all sheets/tables as list of row objects.
Output written to TeamExcels/json/.

Usage:
  python scripts/team_excels_to_json.py

Requires: pip install pandas xlrd openpyxl beautifulsoup4
"""
import json
import math
import os
import re

import pandas as pd
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEAM_EXCELS_DIR = os.path.join(SCRIPT_DIR, "..", "TeamExcels")
OUTPUT_JSON_DIR = os.path.join(TEAM_EXCELS_DIR, "json")


def _json_serialize_value(v):
    """Convert cell value for JSON (NaN/Inf -> None, keep numbers and str)."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, float) and (math.isinf(v) or v != v):
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v == int(v):
            return int(v)
        return v
    return str(v).strip() if isinstance(v, str) else v


def _sheet_to_list_of_dicts(df: pd.DataFrame) -> list[dict]:
    """DataFrame to list of dicts; first row is headers, empty/null headers get col_0, col_1."""
    if df is None or df.empty:
        return []
    # Flatten column names (in case of MultiIndex)
    cols = []
    for i, c in enumerate(df.columns):
        if isinstance(c, tuple):
            name = "_".join(str(x).strip() for x in c if str(x).strip())
        else:
            name = str(c).strip()
        if not name or name == "nan":
            name = f"col_{i}"
        cols.append(name)
    df = df.astype(object).where(pd.notnull(df), None)
    out = []
    for _, row in df.iterrows():
        out.append({cols[j]: _json_serialize_value(row.iloc[j]) for j in range(len(cols))})
    return out


def _safe_filename(path: str) -> str:
    """Base name without extension, safe for JSON filename."""
    base = os.path.splitext(os.path.basename(path))[0]
    base = re.sub(r"[^\w\s\-]", "", base).strip()
    return base or "sheet"


def _html_tables_to_sheets(html_path: str) -> dict[str, list[dict]]:
    """Parse HTML file; each <table> becomes one 'sheet' (list of row dicts)."""
    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    sheets = {}
    for i, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"])
        headers = []
        for j, c in enumerate(header_cells):
            name = (c.get_text() or "").strip()
            if not name:
                name = f"col_{j}"
            headers.append(name)
        data = []
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            row_dict = {}
            for j, c in enumerate(cells):
                key = headers[j] if j < len(headers) else f"col_{j}"
                val = (c.get_text() or "").strip()
                row_dict[key] = _json_serialize_value(val) if val else None
            data.append(row_dict)
        sheet_name = f"Table_{i + 1}"
        sheets[sheet_name] = data
    return sheets


def convert_excel_to_json(excel_path: str, out_dir: str) -> str | None:
    """
    Read one Excel file (all sheets) or HTML-as-.xls; write one JSON file.
    Returns path to written JSON file, or None on error.
    """
    result = {
        "source_file": os.path.basename(excel_path),
        "sheets": {},
    }
    # Try Excel first
    try:
        ext = os.path.splitext(excel_path)[1].lower()
        engine = "xlrd" if ext == ".xls" else None
        all_sheets = pd.read_excel(excel_path, sheet_name=None, header=0, engine=engine)
        if all_sheets:
            for sheet_name, df in all_sheets.items():
                key = str(sheet_name).strip()
                result["sheets"][key] = _sheet_to_list_of_dicts(df)
    except Exception as e:
        err_str = str(e).lower()
        # File may be HTML saved with .xls extension
        if "bof" in err_str or "html" in err_str or "corrupt" in err_str or "expected" in err_str:
            try:
                with open(excel_path, "rb") as f:
                    peek = f.read(200)
                if b"<html" in peek.lower() or b"<!doctype" in peek.lower():
                    result["sheets"] = _html_tables_to_sheets(excel_path)
                else:
                    print(f"  Error reading {excel_path}: {e}")
                    return None
            except Exception as e2:
                print(f"  Error reading {excel_path}: {e2}")
                return None
        else:
            print(f"  Error reading {excel_path}: {e}")
            return None
    if not result["sheets"]:
        print(f"  No sheets/tables in {excel_path}")
        return None
    out_name = _safe_filename(excel_path) + ".json"
    out_path = os.path.join(out_dir, out_name)
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return out_path


def main():
    if not os.path.isdir(TEAM_EXCELS_DIR):
        print(f"Folder not found: {TEAM_EXCELS_DIR}")
        return
    os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)
    extensions = (".xls", ".xlsx")
    files = [
        f
        for f in os.listdir(TEAM_EXCELS_DIR)
        if f.lower().endswith(extensions) and not f.startswith("~")
    ]
    if not files:
        print(f"No .xls or .xlsx files in {TEAM_EXCELS_DIR}")
        return
    print(f"Converting {len(files)} file(s) in {TEAM_EXCELS_DIR} -> {OUTPUT_JSON_DIR}\n")
    for f in sorted(files):
        path = os.path.join(TEAM_EXCELS_DIR, f)
        print(f"  {f} ...")
        out = convert_excel_to_json(path, OUTPUT_JSON_DIR)
        if out:
            print(f"    -> {out}")
    print("\nDone.")


if __name__ == "__main__":
    main()
