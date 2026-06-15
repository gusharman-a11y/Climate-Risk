"""PSE Listed Company Directory.

Two data sources, tried in order:
  1. data/pse_companies.csv  — static file downloaded from the PSE website
     (https://www.pse.com.ph/listed-company-directory/)
     Preferred: has explicit Listing Board column (Main Board / SME Board).

  2. PSE Edge API  — live fetch from edge.pse.com.ph
     Fallback when no local file exists.  Does not expose board classification.

Public API:
    load_pse_companies()      — returns clean DataFrame (file → API)
    fetch_pse_companies()     — live API only (kept for backward compat)
    get_pse_board(row)        — returns "PSE Main Board" or "PSE SME Board"
    PSE_SECTOR_ORDER, PSE_SECTOR_COLORS
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_PAGE_SIZE = 50
_EDGE_URL = "https://edge.pse.com.ph/companyDirectory/search.ax"
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ── Sector normalisation ───────────────────────────────────────────────────────
# The PSE website CSV appends " INDEX" to sectors of index-constituent stocks.
# Strip that and normalise to the display names used in PSE_SECTOR_ORDER.

_SECTOR_NORM: dict[str, str] = {
    "holding firms index":              "Holding Firms",
    "holding firms":                    "Holding Firms",
    "mining & oil index":               "Mining and Oil",
    "mining & oil":                     "Mining and Oil",
    "services index":                   "Services",
    "services":                         "Services",
    "industrial index":                 "Industrial",
    "industrial":                       "Industrial",
    "property index":                   "Property",
    "property":                         "Property",
    "financials index":                 "Financials",
    "financials":                       "Financials",
    "sme":                              "Small, Medium & Emerging Board",
    "sme sector":                       "Small, Medium & Emerging Board",
    "small, medium & emerging board":   "Small, Medium & Emerging Board",
    "etf":                              "ETF",
    "etf-equity":                       "ETF",
    # Sometimes sector is blank for preferred shares / ETFs
}


def _norm_sector(raw: str) -> str:
    key = str(raw).strip().lower()
    # strip trailing " index" first, then look up
    key_no_idx = re.sub(r"\s+index$", "", key)
    return _SECTOR_NORM.get(key, _SECTOR_NORM.get(key_no_idx, str(raw).strip()))


# ── Column maps ────────────────────────────────────────────────────────────────

# PSE website CSV column names (may have trailing spaces)
_FILE_COL_MAP = {
    "company name":   "Company Name",
    "symbol":         "Symbol",
    "sector":         "Sector",
    "sub-sector":     "Subsector",
    "subsector":      "Subsector",
    "sub sector":     "Subsector",
    "listing date":   "Listing Date",
    "date listed":    "Listing Date",
    "listing board":  "Listing Board",
    "board":          "Listing Board",
}

# PSE Edge API column names
_API_COL_MAP = {
    "company name": "Company Name",
    "name":         "Company Name",
    "stock symbol": "Symbol",
    "symbol":       "Symbol",
    "sector":       "Sector",
    "subsector":    "Subsector",
    "sub sector":   "Subsector",
    "listing date": "Listing Date",
    "date listed":  "Listing Date",
}


def _normalise_cols(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in col_map:
            rename[col] = col_map[key]
    return df.rename(columns=rename)


# ── Board / tier helper ────────────────────────────────────────────────────────

def get_pse_board(row: pd.Series) -> str:
    """Return 'PSE Main Board' or 'PSE SME Board' for a company row.

    Checks explicit 'Listing Board' column first; falls back to sector name.
    """
    board = str(row.get("Listing Board", "")).strip().lower()
    if "sme" in board:
        return "PSE SME Board"
    if "main" in board:
        return "PSE Main Board"

    # Fallback: infer from sector
    sector = str(row.get("Sector", "")).strip()
    if sector == "Small, Medium & Emerging Board":
        return "PSE SME Board"

    return "PSE Main Board"


# ── File-based loader ─────────────────────────────────────────────────────────

def load_pse_from_file(file=None) -> pd.DataFrame:
    """Load PSE company list from a local file.

    file : path-like, file-like (with .name), or None.
    Falls back to data/pse_companies.csv if None.
    Returns empty DataFrame if nothing found.
    """
    if file is None:
        for fname in ("pse_companies.csv", "pse_companies.xlsx"):
            p = DATA_DIR / fname
            if p.exists() and p.stat().st_size > 1024:
                file = p
                break

    if file is None:
        return pd.DataFrame()

    try:
        if isinstance(file, Path):
            df = pd.read_excel(file) if file.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(file)
        else:
            name = getattr(file, "name", "").lower()
            df = pd.read_excel(file) if name.endswith((".xlsx", ".xls")) else pd.read_csv(file)
    except Exception:
        return pd.DataFrame()

    df = _normalise_cols(df, _FILE_COL_MAP)

    if "Company Name" not in df.columns:
        return pd.DataFrame()

    # Clean strings
    df["Company Name"] = df["Company Name"].astype(str).str.strip()
    df = df[
        df["Company Name"].notna()
        & (df["Company Name"] != "")
        & (df["Company Name"] != "nan")
    ]

    if "Symbol" in df.columns:
        df["Symbol"] = df["Symbol"].astype(str).str.strip()

    # Normalise sectors
    if "Sector" in df.columns:
        df["Sector"] = df["Sector"].apply(_norm_sector)

    if "Subsector" in df.columns:
        df["Subsector"] = df["Subsector"].astype(str).str.strip()

    # Parse listing date
    if "Listing Date" in df.columns:
        df["Listing Date"] = pd.to_datetime(
            df["Listing Date"].astype(str).str.strip(), errors="coerce", dayfirst=False
        )

    # Add PSE Edge link
    if "Symbol" in df.columns and "PSE Link" not in df.columns:
        df["PSE Link"] = df["Symbol"].apply(
            lambda s: f"https://edge.pse.com.ph/companyPage/stockData.do?cmpy_id={s}"
            if pd.notna(s) and str(s).strip() not in ("", "nan") else ""
        )

    return df.reset_index(drop=True)


# ── Live API loader ────────────────────────────────────────────────────────────

class _TableParser(HTMLParser):
    """Extracts rows from the first <table> found in an HTML string."""

    def __init__(self):
        super().__init__()
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self.rows: list[list[str]] = []
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table = True
            self._depth += 1
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._current_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag):
        if tag == "table":
            self._depth -= 1
            if self._depth == 0:
                self._in_table = False
        elif tag == "tr" and self._in_table:
            if self._current_row:
                self.rows.append(self._current_row)
            self._in_row = False
        elif tag in ("td", "th") and self._in_row:
            self._current_row.append(" ".join(self._current_cell).strip())
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell.append(data)


def _parse_table(html: str) -> list[list[str]]:
    p = _TableParser()
    p.feed(html)
    return p.rows


def _rows_to_df(rows: list[list[str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    header = rows[0]
    data = rows[1:]
    if not data:
        return pd.DataFrame()
    n = len(header)
    data = [r[:n] + [""] * max(0, n - len(r)) for r in data]
    return pd.DataFrame(data, columns=header)


def fetch_pse_companies(max_pages: int = 10, timeout: int = 30) -> pd.DataFrame:
    """Fetch the full PSE Listed Company Directory from the Edge API (live).

    Returns a DataFrame with columns:
        Company Name, Symbol, Sector, Subsector, Listing Date, PSE Link

    No Listing Board column — use load_pse_companies() if you need board info.
    """
    all_dfs: list[pd.DataFrame] = []

    for page in range(1, max_pages + 1):
        resp = requests.get(
            _EDGE_URL,
            params={
                "method": "fetchAllListedCompanies",
                "pageNo": page,
                "itemsPerPage": _PAGE_SIZE,
            },
            headers={"User-Agent": _UA},
            timeout=timeout,
        )
        resp.raise_for_status()

        rows = _parse_table(resp.text)
        df = _rows_to_df(rows)
        if df.empty:
            break

        df = _normalise_cols(df, _API_COL_MAP)

        if "Company Name" in df.columns:
            df = df[
                df["Company Name"].notna()
                & (df["Company Name"].str.strip() != "")
                & (~df["Company Name"].str.lower().str.contains(
                    r"company\s*name|next|prev", regex=True
                ))
            ]

        if df.empty:
            break

        if "Sector" in df.columns:
            df["Sector"] = df["Sector"].apply(_norm_sector)

        all_dfs.append(df)

        if len(df) < _PAGE_SIZE - 5:
            break

    if not all_dfs:
        return pd.DataFrame()

    result = pd.concat(all_dfs, ignore_index=True)

    if "Symbol" in result.columns:
        result["PSE Link"] = result["Symbol"].apply(
            lambda s: f"https://edge.pse.com.ph/companyPage/stockData.do?cmpy_id={s}"
            if pd.notna(s) and s else ""
        )

    if "Listing Date" in result.columns:
        result["Listing Date"] = pd.to_datetime(
            result["Listing Date"], errors="coerce", format="mixed"
        )

    return result.reset_index(drop=True)


def load_pse_companies(max_pages: int = 10, timeout: int = 30) -> pd.DataFrame:
    """Load PSE company list: file first (preferred), then live API fallback.

    The file source (data/pse_companies.csv) includes explicit Listing Board
    classification; the live API does not.
    """
    df = load_pse_from_file()
    if not df.empty:
        return df
    return fetch_pse_companies(max_pages=max_pages, timeout=timeout)


# ── Sector display constants ───────────────────────────────────────────────────

PSE_SECTOR_ORDER = [
    "Financials",
    "Holding Firms",
    "Industrial",
    "Property",
    "Services",
    "Mining and Oil",
    "Small, Medium & Emerging Board",
    "ETF",
]

PSE_SECTOR_COLORS = {
    "Financials":                       "#0369A1",
    "Holding Firms":                    "#0891B2",
    "Industrial":                       "#059669",
    "Property":                         "#7C3AED",
    "Services":                         "#D97706",
    "Mining and Oil":                   "#DC2626",
    "Small, Medium & Emerging Board":   "#6B7280",
    "ETF":                              "#9CA3AF",
}
