"""ASX-listed companies lookup.

Loads data/ASXListedCompanies.csv (official ASX listings export) and provides
helpers to:
  - Check whether a company is currently ASX-listed
  - Look up its ASX code by company name (fuzzy match)
  - Add ASX Code + ASX Listed columns to a cohort dataframe

The lookup is the authoritative answer to 'is this company on the ASX?' —
more reliable than ISIN-prefix inference (handles dual-listed entities,
recently-renamed companies, and the 'Limited' / 'Group' / 'Ltd' variations).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ASX_CSV = DATA_DIR / "ASXListedCompanies.csv"


def _name_key(name: str) -> str:
    """Normalise for matching — same logic as researched.py for consistency."""
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    for tok in ("limited", "ltd", "pty", "group holdings", "holdings", "group",
                "corporation", "corp", "plc", "the", "australia", "australian",
                "and", "&"):
        n = re.sub(rf"\b{re.escape(tok)}\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def load_asx_listings() -> pd.DataFrame:
    """Load the ASX listings file. Returns empty df if missing.
    File format: row 0 is a date header, row 2 is the column header."""
    if not ASX_CSV.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(ASX_CSV, skiprows=2)
        df.columns = [c.strip() for c in df.columns]
        # Standardise column names
        rename = {}
        for c in df.columns:
            lc = c.lower()
            if "company" in lc or "name" in lc:
                rename[c] = "Company Name"
            elif "code" in lc or "ticker" in lc:
                rename[c] = "ASX Code"
            elif "industry" in lc or "gics" in lc:
                rename[c] = "GICS Industry Group"
        df = df.rename(columns=rename)
        df["_key"] = df["Company Name"].apply(_name_key)
        return df
    except Exception:
        return pd.DataFrame()


def attach_asx_listing(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'ASX Code', 'ASX Listed', and refined 'GICS Industry Group' columns.

    Matches each row's Company Name against the ASX listings via normalised
    name key. ASX Code is set when a match is found; ASX Listed = 'Yes'/'No'.
    """
    if df.empty:
        return df
    listings = load_asx_listings()
    if listings.empty:
        df = df.copy()
        df["ASX Code"] = ""
        df["ASX Listed"] = "Unknown"
        return df

    listings_by_key = listings.set_index("_key")[["Company Name", "ASX Code", "GICS Industry Group"]]

    df = df.copy()
    df["_match_key"] = df["Company Name"].apply(_name_key)

    def _lookup(k):
        if not k or k not in listings_by_key.index:
            return pd.Series({"ASX Code": "", "ASX Listed": "No", "GICS (ASX)": ""})
        row = listings_by_key.loc[k]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        return pd.Series({
            "ASX Code": str(row.get("ASX Code", "")).strip(),
            "ASX Listed": "Yes",
            "GICS (ASX)": str(row.get("GICS Industry Group", "")).strip(),
        })

    lookups = df["_match_key"].apply(_lookup)
    df["ASX Code"] = lookups["ASX Code"]
    df["ASX Listed"] = lookups["ASX Listed"]
    df["GICS (ASX)"] = lookups["GICS (ASX)"]
    return df.drop(columns=["_match_key"])
