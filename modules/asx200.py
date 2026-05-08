"""ASX 200 non-SBTi cohort — Phase 3 expansion.

Companies in this dataset are ASX-listed but do NOT have an SBTi-validated
target. The BD signal is the inverse of the SBTi cohort: they face ASRS
disclosure obligations now and SBTi-style scrutiny soon, but lack a
credible validated target. Pollination's pitch: help them set one.

Target classifications:
  - SBTi committed (intent letter, no validated target yet)
  - Quantitative non-validated (specific %/year reduction, not SBTi)
  - Net-zero only (long-term aspiration, no near-term quantification)
  - Aspirational (vague climate ambition, no specifics)
  - No public target

Best-effort classifications below come from public disclosures in training
data; mark each as "needs verification" before client-facing use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ASX200_CSV = DATA_DIR / "asx200_non_sbti.csv"


TARGET_CLASS_ORDER = [
    "SBTi committed",
    "Quantitative non-validated",
    "Net-zero only",
    "Aspirational",
    "No public target",
]

# Higher = stronger BD signal (further from a credible validated target).
TARGET_CLASS_BD_PRIORITY = {
    "SBTi committed": 1,            # Already engaged with SBTi — soft target
    "Quantitative non-validated": 2,  # Has data but needs validation
    "Net-zero only": 3,             # Has aspiration but needs near-term
    "Aspirational": 4,              # Major gap
    "No public target": 5,          # Largest gap; ASRS will force this
}

TARGET_CLASS_COLOUR = {
    "SBTi committed": "#16A34A",
    "Quantitative non-validated": "#65A30D",
    "Net-zero only": "#D97706",
    "Aspirational": "#DC2626",
    "No public target": "#7F1D1D",
}


def load_asx200() -> pd.DataFrame:
    """Load the curated ASX 200 non-SBTi list. Returns empty DataFrame if file
    missing."""
    if not ASX200_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(ASX200_CSV)
    df.columns = [c.strip() for c in df.columns]
    return df


def to_phase1_shape(asx200: pd.DataFrame) -> pd.DataFrame:
    """Adapt the ASX 200 data to the same column shape used by the SBTi screen,
    so the Streamlit UI can display both cohorts with one set of code paths."""
    if asx200.empty:
        return asx200

    # Map to canonical SBTi-style columns where possible
    mapped = pd.DataFrame()
    mapped["Company Name"] = asx200["Company Name"]
    mapped["ISIN"] = asx200.get("ASX Code", "").astype(str).apply(
        lambda c: f"AU000000{c.upper()}".ljust(12, "0")[:12] if c and c != "nan" else ""
    )
    mapped["Country"] = "Australia"
    mapped["Region"] = "Oceania"
    mapped["Sector"] = asx200.get("GICS Sector", asx200.get("Sector", ""))
    mapped["Industry"] = asx200.get("GICS Industry", "")
    mapped["Organization Type"] = asx200.get("Org Type", "Corporate")
    mapped["Near-term Status"] = ""           # Not applicable — no SBTi target
    mapped["Long-term Status"] = ""
    mapped["Net-Zero Status"] = ""
    mapped["Target"] = asx200.get("Stated Target Description", "")
    mapped["Target Year"] = asx200.get("Stated Target Year", pd.NA)
    mapped["Net-Zero Year"] = asx200.get("Stated Net-Zero Year", pd.NA)
    mapped["Long-term Target Year"] = pd.NA
    mapped["Target Classification"] = asx200.get("Target Classification", "No public target")
    mapped["Target Classification (Long)"] = asx200.get("Target Classification", "No public target")
    mapped["Date Updated"] = pd.NA

    # Carry through extras specific to this cohort
    mapped["ASX Code"] = asx200.get("ASX Code", "")
    mapped["Market Cap Tier"] = asx200.get("Market Cap Tier", "")
    mapped["Source URL"] = asx200.get("Source URL", "")
    mapped["Notes"] = asx200.get("Notes", "")
    mapped["Target Classification (BD)"] = mapped["Target Classification"]
    mapped["BD Priority"] = mapped["Target Classification"].map(TARGET_CLASS_BD_PRIORITY).fillna(5).astype(int)
    # Compute ASRS Tier from Market Cap Tier (Mega/Large = Group 1; Mid = Group 2)
    from modules.sbti import asrs_tier
    mapped["ASRS Tier"] = mapped.apply(asrs_tier, axis=1)
    return mapped
