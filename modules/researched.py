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
METADATA_CSV = DATA_DIR / "sbti_target_metadata.csv"


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


def _clean_classification(v) -> str:
    """ChatGPT sometimes returns 'SBTi committed — submitted intent letter…'.
    Strip the em-dash/hyphen suffix to keep just the canonical category."""
    s = str(v or "").strip()
    for sep in (" — ", " – ", " - "):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break
    return s


def load_metadata() -> pd.DataFrame:
    """Read data/sbti_target_metadata.csv (qualitative companion file from
    the new prompt schema: Latest S1/S2, Scope 3 Status, Recent Update,
    BD Signals). Returns empty df if file missing."""
    if not METADATA_CSV.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(METADATA_CSV)
        df.columns = [c.strip() for c in df.columns]
        df["_key"] = df["Company Name"].apply(_name_key)
        return df
    except Exception:
        return pd.DataFrame()


def apply_overlay(df: pd.DataFrame) -> pd.DataFrame:
    """For each row in df whose Company Name matches a researched entry,
    override Target / Target Year / Net-Zero Year / Target Classification /
    plus add Research-prefixed columns for traceability (Confidence, URL,
    Notes, Scope 3 Status, Recent Update, BD Signals)."""
    if df.empty:
        return df

    work = df.copy()
    work["_key"] = work["Company Name"].apply(_name_key)

    # Default columns
    work["Researched"] = False
    work["Research Confidence"] = ""
    work["Research Source URL"] = ""
    work["Research Notes"] = ""
    work["Scope 3 Status"] = ""
    work["Recent Update"] = ""
    work["BD Signals"] = ""

    # 1) Apply the primary research file (target classification)
    overlay = load_researched()
    if not overlay.empty:
        overlay_indexed = overlay.set_index("_key")
        for idx, row in work.iterrows():
            key = row["_key"]
            if not key or key not in overlay_indexed.index:
                continue
            ovl = overlay_indexed.loc[key]
            if isinstance(ovl, pd.DataFrame):
                ovl = ovl.iloc[0]
            work.at[idx, "Target"] = str(ovl.get("Stated Target Description", "")).strip()
            ty = _coerce_year(ovl.get("Stated Target Year"))
            nz = _coerce_year(ovl.get("Stated Net-Zero Year"))
            if ty is not pd.NA:
                # Write to both the raw Target Year (SBTi column) and the
                # computed Target Year (used) — the latter is what shows in the
                # cohort table and feeds the trajectory math.
                work.at[idx, "Target Year"] = ty
                work.at[idx, "Target Year (used)"] = ty
                work.at[idx, "Year Source"] = "researched (near-term)"
                # Refresh Years to Target so the column matches the new year
                import datetime as _dt
                work.at[idx, "Years to Target"] = int(ty) - _dt.datetime.utcnow().year
            if nz is not pd.NA:
                work.at[idx, "Net-Zero Year"] = nz
            # If only net-zero year is set (no near-term), fall back to that
            # for the displayed Target Year (used) and tag the source.
            if ty is pd.NA and nz is not pd.NA and pd.isna(work.at[idx, "Target Year (used)"]):
                work.at[idx, "Target Year (used)"] = nz
                work.at[idx, "Year Source"] = "researched (net-zero)"
                import datetime as _dt
                work.at[idx, "Years to Target"] = int(nz) - _dt.datetime.utcnow().year
            cls = _clean_classification(ovl.get("Target Classification", ""))
            if cls:
                work.at[idx, "Target Classification"] = cls
                work.at[idx, "Target Classification (Long)"] = cls
            work.at[idx, "Researched"] = True
            work.at[idx, "Research Confidence"] = str(ovl.get("Confidence", "")).strip()
            work.at[idx, "Research Source URL"] = str(ovl.get("Source URL", "")).strip()
            work.at[idx, "Research Notes"] = str(ovl.get("Notes", "")).strip()

    # 2) Apply the metadata file (qualitative BD signals)
    meta = load_metadata()
    if not meta.empty:
        meta_indexed = meta.set_index("_key")
        for idx, row in work.iterrows():
            key = row["_key"]
            if not key or key not in meta_indexed.index:
                continue
            m = meta_indexed.loc[key]
            if isinstance(m, pd.DataFrame):
                m = m.iloc[0]
            work.at[idx, "Researched"] = True
            work.at[idx, "Scope 3 Status"] = str(m.get("Scope 3 Status", "")).strip()
            work.at[idx, "Recent Update"] = str(m.get("Recent Update", "")).strip()
            work.at[idx, "BD Signals"] = str(m.get("BD Signals", "")).strip()
            # Only fill confidence / URL / notes if the primary file didn't
            if not work.at[idx, "Research Confidence"]:
                work.at[idx, "Research Confidence"] = str(m.get("Confidence", "")).strip()
            if not work.at[idx, "Research Source URL"]:
                work.at[idx, "Research Source URL"] = str(m.get("Source URL", "")).strip()

    return work.drop(columns=["_key"])
