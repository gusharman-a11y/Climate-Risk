"""PSE Listed Company Directory — live fetch from the PSE Edge API.

Source: https://edge.pse.com.ph/companyDirectory/search.ax
Fetches all pages (50 companies per page) and returns a clean DataFrame.
No external dependencies beyond requests + pandas (built-in html.parser used).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from functools import lru_cache

import pandas as pd
import requests

_EDGE_URL = "https://edge.pse.com.ph/companyDirectory/search.ax"
_PAGE_SIZE = 50
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ── Minimal HTML table parser (avoids lxml/beautifulsoup4 dependency) ─────────

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
        elif tag in ("tr",) and self._in_table:
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
    # First row is often the header
    header = rows[0]
    data = rows[1:]
    if not data:
        return pd.DataFrame()
    # Pad/truncate rows to header length
    n = len(header)
    data = [r[:n] + [""] * max(0, n - len(r)) for r in data]
    return pd.DataFrame(data, columns=header)


# ── Column normalisation ───────────────────────────────────────────────────────

_COL_MAP = {
    "company name": "Company Name",
    "name": "Company Name",
    "stock symbol": "Symbol",
    "symbol": "Symbol",
    "sector": "Sector",
    "subsector": "Subsector",
    "sub sector": "Subsector",
    "listing date": "Listing Date",
    "date listed": "Listing Date",
}


def _normalise_cols(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in _COL_MAP:
            rename[col] = _COL_MAP[key]
    return df.rename(columns=rename)


# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch_pse_companies(max_pages: int = 10, timeout: int = 30) -> pd.DataFrame:
    """Fetch the full PSE Listed Company Directory from the Edge API.

    Returns a DataFrame with columns:
        Company Name, Symbol, Sector, Subsector, Listing Date, PSE Link

    Fetches up to `max_pages` pages of `_PAGE_SIZE` companies each.
    Raises on network errors; returns empty DataFrame if parsing fails.
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

        df = _normalise_cols(df)

        # Drop rows that are clearly header repeats or navigation artefacts
        if "Company Name" in df.columns:
            df = df[
                df["Company Name"].notna()
                & (df["Company Name"].str.strip() != "")
                & (~df["Company Name"].str.lower().str.contains(r"company\s*name|next|prev", regex=True))
            ]

        if df.empty:
            break

        all_dfs.append(df)

        # Last page is shorter than a full page
        if len(df) < _PAGE_SIZE - 5:   # -5 tolerance for partial pages
            break

    if not all_dfs:
        return pd.DataFrame()

    result = pd.concat(all_dfs, ignore_index=True)

    # Add direct link to PSE edge company info
    if "Symbol" in result.columns:
        result["PSE Link"] = result["Symbol"].apply(
            lambda s: f"https://edge.pse.com.ph/companyPage/stockData.do?cmpy_id={s}"
            if pd.notna(s) and s else ""
        )

    # Parse listing date to datetime for sorting
    if "Listing Date" in result.columns:
        result["Listing Date"] = pd.to_datetime(
            result["Listing Date"], errors="coerce", format="mixed"
        )

    return result.reset_index(drop=True)


# ── Sector taxonomy helpers ────────────────────────────────────────────────────

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
