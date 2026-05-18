"""Bursa Malaysia Listed Company data loader.

Bursa Malaysia's public APIs are blocked from automated access (403/CORS).
This module loads company data from:
  1. A user-uploaded file (passed from the Streamlit UI)
  2. data/bursa_companies.{csv,xlsx} committed to the repo
  3. Returns empty DataFrame if neither is available (tab prompts upload)

Expected file columns (flexible — normalised on load):
  Company Name (or Name / Stock Name)
  Symbol (or Code / Stock Code)
  Market (or Board / Listing Board)   → "Main Market", "ACE Market", "LEAP Market"
  Sector (or Industry Classification)
  ISIN (or ISIN Code)
  Listing Date (or Date Listed)

How to get the Bursa company list:
  1. Go to https://www.bursamalaysia.com/market/listed-companies/list-of-listed-company/listed_companies_directory
  2. Select "Download" → CSV or Excel
  3. Upload via the Malaysia tab in this app.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

BURSA_MARKET_ORDER = ["Main Market", "ACE Market", "LEAP Market"]

BURSA_MARKET_COLORS = {
    "Main Market": "#0369A1",
    "ACE Market":  "#0891B2",
    "LEAP Market": "#6B7280",
}

_COL_MAP = {
    "company name":            "Company Name",
    "name":                    "Company Name",
    "company":                 "Company Name",
    "stock name":              "Company Name",
    "stock short name":        "Company Name",
    "listed company":          "Company Name",
    "symbol":                  "Symbol",
    "code":                    "Symbol",
    "stock code":              "Symbol",
    "trading name":            "Symbol",
    "short name":              "Symbol",
    "market":                  "Market",
    "board":                   "Market",
    "listing board":           "Market",
    "exchange":                "Market",
    "sector":                  "Sector",
    "industry classification": "Sector",
    "industry":                "Sector",
    "isin":                    "ISIN",
    "isin code":               "ISIN",
    "listing date":            "Listing Date",
    "date listed":             "Listing Date",
    "date of listing":         "Listing Date",
}


def _normalise_cols(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in _COL_MAP:
            rename[col] = _COL_MAP[key]
    return df.rename(columns=rename)


def _normalise_market(market: str) -> str:
    m = str(market).strip().lower()
    if "leap" in m:
        return "LEAP Market"
    if "ace" in m:
        return "ACE Market"
    if "main" in m:
        return "Main Market"
    return str(market).strip() or "Main Market"


def load_bursa_companies(file=None) -> pd.DataFrame:
    """Load Bursa Malaysia company list.

    Parameters
    ----------
    file : file-like or None
        Uploaded file (BytesIO with .name attribute) or None.
        Falls back to data/bursa_companies.{csv,xlsx} if None.

    Returns
    -------
    pd.DataFrame with standardised columns, or empty DataFrame if no data found.
    """
    df: pd.DataFrame | None = None

    if file is not None:
        try:
            name = getattr(file, "name", "").lower()
            if name.endswith((".xlsx", ".xls")):
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)
        except Exception:
            return pd.DataFrame()
    else:
        for fname in ("bursa_companies.csv", "bursa_companies.xlsx"):
            p = DATA_DIR / fname
            if p.exists() and p.stat().st_size > 1024:
                df = pd.read_excel(p) if p.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(p)
                break

    if df is None or df.empty:
        return pd.DataFrame()

    df = _normalise_cols(df)

    if "Company Name" in df.columns:
        df["Company Name"] = df["Company Name"].astype(str).str.strip()
        df = df[df["Company Name"].notna() & (df["Company Name"] != "") & (df["Company Name"] != "nan")]

    if "Market" in df.columns:
        df["Market"] = df["Market"].apply(_normalise_market)

    if "Listing Date" in df.columns:
        df["Listing Date"] = pd.to_datetime(df["Listing Date"], errors="coerce", dayfirst=True)

    # Add Bursa company page link if Symbol present
    if "Symbol" in df.columns and "Bursa Link" not in df.columns:
        df["Bursa Link"] = df["Symbol"].apply(
            lambda s: f"https://www.bursamalaysia.com/trade/trading_resources/listing_directory/company-profile?stock_code={s}"
            if pd.notna(s) and str(s).strip() else ""
        )

    return df.reset_index(drop=True)


def get_bursa_tier(row: pd.Series) -> str:
    """Return Bursa market tier label for a company row."""
    market = str(row.get("Market", "")).strip()
    if market in BURSA_MARKET_ORDER:
        return market
    return "Main Market"


def is_available() -> bool:
    """Return True if a Bursa company list file exists locally."""
    for fname in ("bursa_companies.csv", "bursa_companies.xlsx"):
        p = DATA_DIR / fname
        if p.exists() and p.stat().st_size > 1024:
            return True
    return False
