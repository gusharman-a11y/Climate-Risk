"""Researched-target overlay.

Merges data/climate_targets_research.csv (verified target data from external
research, e.g. ChatGPT/Claude.ai web search) onto the cohort. Applies across
every cohort — wherever a company name matches, the researched target
overrides any training-data seed or SBTi-derived target wording.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESEARCH_CSV = DATA_DIR / "climate_targets_research.csv"


def _name_key(name: str) -> str:
    """Normalise a company name for matching: lowercase, strip punctuation +
    common corporate suffixes, collapse whitespace."""
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    for tok in ("limited", "ltd", "pty", "group holdings", "holdings", "group",
                "corporation", "corp", "plc", "the", "australia", "australian",
                "and", "&"):
        n = re.sub(rf"\b{re.escape(tok)}\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def load_researched() -> pd.DataFrame:
    if not RESEARCH_CSV.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(RESEARCH_CSV)
        df.columns = [c.strip() for c in df.columns]
        df["_key"] = df["Company Name"].apply(_name_key)
        return df
    except Exception:
        return pd.DataFrame()


def _coerce_year(v) -> object:
    """Treat 'N/A' / 'n/a' / '' / None as missing; otherwise keep the int."""
    if v is None:
        return pd.NA
    s = str(v).strip()
    if not s or s.lower() in ("n/a", "na", "nan", "none", "—"):
        return pd.NA
    m = re.search(r"(19|20)\d{2}", s)
    return int(m.group(0)) if m else pd.NA


def apply_overlay(df: pd.DataFrame) -> pd.DataFrame:
    """For each row in df whose Company Name matches a researched entry,
    override Target / Target Year / Net-Zero Year / Target Classification /
    plus add Research-prefixed columns for traceability (Confidence, URL, Notes)."""
    if df.empty:
        return df
    overlay = load_researched()
    if overlay.empty:
        df["Researched"] = False
        return df

    work = df.copy()
    work["_key"] = work["Company Name"].apply(_name_key)
    overlay_indexed = overlay.set_index("_key")

    # Default columns
    work["Researched"] = False
    work["Research Confidence"] = ""
    work["Research Source URL"] = ""
    work["Research Notes"] = ""

    for idx, row in work.iterrows():
        key = row["_key"]
        if not key or key not in overlay_indexed.index:
            continue
        ovl = overlay_indexed.loc[key]
        if isinstance(ovl, pd.DataFrame):
            ovl = ovl.iloc[0]
        # Override target fields
        work.at[idx, "Target"] = str(ovl.get("Stated Target Description", "")).strip()
        ty = _coerce_year(ovl.get("Stated Target Year"))
        nz = _coerce_year(ovl.get("Stated Net-Zero Year"))
        if ty is not pd.NA:
            work.at[idx, "Target Year"] = ty
        if nz is not pd.NA:
            work.at[idx, "Net-Zero Year"] = nz
        cls = str(ovl.get("Target Classification", "")).strip()
        if cls:
            work.at[idx, "Target Classification"] = cls
            work.at[idx, "Target Classification (Long)"] = cls
        work.at[idx, "Researched"] = True
        work.at[idx, "Research Confidence"] = str(ovl.get("Confidence", "")).strip()
        work.at[idx, "Research Source URL"] = str(ovl.get("Source URL", "")).strip()
        work.at[idx, "Research Notes"] = str(ovl.get("Notes", "")).strip()

    return work.drop(columns=["_key"])
