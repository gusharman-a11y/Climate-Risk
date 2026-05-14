"""Safeguard Mechanism data integration.

Loads the CER Safeguard baselines-and-emissions CSV and matches companies
in the SBTi cohort to their Safeguard-covered facilities.

Data source: CER Safeguard Mechanism register
  https://cer.gov.au/markets/reports-and-data/safeguard-mechanism

To use: copy the baselines-and-emissions.csv from the Safeguard register
into data/safeguard_baselines.csv, OR set SAFEGUARD_CSV env var to the
full path (e.g. pointing at the pollination-carbon-tracker data directory).

The file is published annually by CER, typically within ~3 months of FY end.
Current snapshot: FY2024-25.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── Path resolution ────────────────────────────────────────────────────────────

def _csv_path() -> Path | None:
    env = os.environ.get("SAFEGUARD_CSV")
    if env:
        p = Path(env)
        return p if p.exists() else None
    # Try local data/ directory first
    local = DATA_DIR / "safeguard_baselines.csv"
    if local.exists():
        return local
    # Try to find it in a sibling carbon-tracker project
    for sibling in DATA_DIR.parent.parent.glob("*/data/raw/cer/safeguard/*/baselines-and-emissions.csv"):
        return sibling
    return None


# ── Parsing utilities ──────────────────────────────────────────────────────────

def _parse_num(val) -> float | None:
    if pd.isna(val):
        return None
    s = str(val).replace(",", "").replace(" -   ", "").strip()
    if not s or s in ("-", "n/a", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ── Data loader ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_safeguard() -> pd.DataFrame:
    """Load and parse the Safeguard baselines-and-emissions CSV.
    Returns an empty DataFrame if the file is not found."""
    path = _csv_path()
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    str_cols = {
        "Facility name": "facility_name",
        "Responsible emitter": "responsible_emitter",
        "State/Territory of operation": "state",
        "Notes": "notes",
    }
    for raw, alias in str_cols.items():
        if raw in df.columns:
            df[alias] = df[raw].str.strip()
        else:
            df[alias] = ""

    num_cols = {
        "Baseline emissions number": "baseline",
        "Covered emissions": "covered_emissions",
        "ACCUs issued": "accus_issued",
        "ACCUs deemed surrendered": "accus_deemed_surrendered",
        "ACCUs surrendered": "accus_surrendered",
        "SMCs surrendered": "smcs_surrendered",
        "Net emissions number": "net_emissions",
        "Net position number": "net_position",
        "ERC": "erc",
        "GHG Carbon dioxide": "ghg_co2",
        "GHG Methane": "ghg_ch4",
        "GHG Nitrous oxide": "ghg_n2o",
        "GHG Other": "ghg_other",
    }
    for raw, alias in num_cols.items():
        if raw in df.columns:
            df[alias] = df[raw].apply(_parse_num)
        else:
            df[alias] = None

    # Total surrendered = ACCUs + SMCs
    df["total_surrendered"] = (
        df["accus_surrendered"].fillna(0) + df["smcs_surrendered"].fillna(0)
    )
    # Compliance shortfall (positive = above baseline, must surrender more)
    df["net_position"] = df["net_position"]  # keep as-is: + = surplus, - = shortfall

    # Normalised emitter key for matching
    df["_emitter_key"] = df["responsible_emitter"].apply(_name_key)

    return df.reset_index(drop=True)


# ── Name normalisation ─────────────────────────────────────────────────────────

_STRIP_TOKENS = (
    "limited", "ltd", "pty", "group holdings", "holdings",
    "corporation", "corp", "plc", "the", "australia", "australian", "and",
    # don't strip "group" alone — it's distinctive for some names
)


def _name_key(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    for tok in _STRIP_TOKENS:
        n = re.sub(rf"\b{re.escape(tok)}\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def _name_match(company_key: str, emitter_key: str) -> bool:
    """True if the company name plausibly refers to the same entity as the
    Safeguard emitter. Matching rules:
    1. Exact normalized key match.
    2. First token matches AND ≥2 tokens overlap (catches subsidiaries like
       "AGL Energy" → "AGL Energy Generation Pty Ltd").
    3. Company key is a leading substring of the emitter key (≥6 chars).
    """
    if not company_key or not emitter_key:
        return False
    if company_key == emitter_key:
        return True

    c_tokens = company_key.split()
    e_tokens = emitter_key.split()
    if not c_tokens or not e_tokens:
        return False

    # Rule 2: first token matches + overlap count
    if c_tokens[0] == e_tokens[0]:
        overlap = len(set(c_tokens) & set(e_tokens))
        needed = min(2, len(c_tokens))
        if overlap >= needed:
            return True

    # Rule 3: company key prefix in emitter key (handles short distinctive names)
    if len(company_key) >= 6 and emitter_key.startswith(company_key[:6]):
        return True

    return False


# ── Company lookup ─────────────────────────────────────────────────────────────

def find_facilities(company_name: str) -> pd.DataFrame:
    """Return all Safeguard facilities whose responsible emitter matches the
    given company name. Returns empty DataFrame if no match or no data."""
    df = load_safeguard()
    if df.empty or not company_name:
        return pd.DataFrame()
    key = _name_key(company_name)
    if not key:
        return pd.DataFrame()
    mask = df["_emitter_key"].apply(lambda ek: _name_match(key, ek))
    return df[mask].copy()


def aggregate(company_name: str) -> dict | None:
    """Return aggregated Safeguard stats for a company, or None if not covered."""
    facs = find_facilities(company_name)
    if facs.empty:
        return None

    def _sum(col: str) -> float:
        return float(facs[col].fillna(0).sum())

    baseline = _sum("baseline")
    covered = _sum("covered_emissions")
    surrendered = _sum("total_surrendered")
    net_position = _sum("net_position")    # + = below baseline (surplus), - = above (shortfall)

    return {
        "facility_count": len(facs),
        "baseline_tco2e": baseline,
        "covered_tco2e": covered,
        "total_surrendered_tco2e": surrendered,
        "net_position_tco2e": net_position,
        "net_position_label": "⬇ Below baseline (compliant)" if net_position >= 0 else "⬆ Above baseline (shortfall)",
        "accus_surrendered_tco2e": _sum("accus_surrendered"),
        "smcs_surrendered_tco2e": _sum("smcs_surrendered"),
        "facilities": facs,
    }


def is_available() -> bool:
    """Return True if the Safeguard CSV is accessible."""
    return _csv_path() is not None
