"""Voluntary ACCU retirement matching.

Loads the ANREU voluntary-cancellations CSV and matches entities to
companies in the SBTi cohort using the same fuzzy name-matching approach
as modules/safeguard.py.

Data source: CER ANREU voluntary cancellations register
  https://cer.gov.au/markets/reports-and-data/anreu-account-information
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_STRIP_TOKENS = (
    "limited", "ltd", "pty", "group holdings", "holdings",
    "corporation", "corp", "plc", "the", "australia", "australian", "and",
)


def _csv_path() -> Path | None:
    env = os.environ.get("VOLUNTARY_CSV")
    if env:
        p = Path(env)
        return p if p.exists() else None
    bundled = DATA_DIR / "cer" / "voluntary-cancellations.csv"
    if bundled.exists():
        return bundled
    for sibling in DATA_DIR.parent.parent.glob("*/data/raw/cer/anreu/voluntary-cancellations/*/voluntary-cancellations.csv"):
        return sibling
    return None


def _name_key(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    for tok in _STRIP_TOKENS:
        n = re.sub(rf"\b{re.escape(tok)}\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def _name_match(company_key: str, emitter_key: str) -> bool:
    if not company_key or not emitter_key:
        return False
    if company_key == emitter_key:
        return True
    c_tokens = company_key.split()
    e_tokens = emitter_key.split()
    if not c_tokens or not e_tokens:
        return False
    if c_tokens[0] == e_tokens[0]:
        overlap = len(set(c_tokens) & set(e_tokens))
        needed = min(2, len(c_tokens))
        if overlap >= needed:
            return True
    if len(company_key) >= 6 and emitter_key.startswith(company_key[:6]):
        return True
    return False


@lru_cache(maxsize=1)
def load_voluntary() -> pd.DataFrame:
    """Load and aggregate voluntary cancellations by entity.
    Returns empty DataFrame if file not found."""
    path = _csv_path()
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    # Normalise columns
    entity_col = next((c for c in df.columns if "entity" in c.lower()), None)
    units_col = next((c for c in df.columns if "number" in c.lower() or "units" in c.lower()), None)

    if entity_col is None or units_col is None:
        return pd.DataFrame()

    df = df.rename(columns={entity_col: "entity_name", units_col: "units"})
    df["units"] = pd.to_numeric(df["units"].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    # Aggregate by entity
    agg = df.groupby("entity_name", as_index=False)["units"].sum()
    agg["_entity_key"] = agg["entity_name"].apply(_name_key)
    return agg.reset_index(drop=True)


def voluntary_retirements(company_name: str) -> float | None:
    """Return total voluntary ACCUs retired by this company, or None if no match."""
    df = load_voluntary()
    if df.empty or not company_name:
        return None
    key = _name_key(company_name)
    if not key:
        return None
    matched = df[df["_entity_key"].apply(lambda ek: _name_match(key, ek))]
    if matched.empty:
        return None
    return float(matched["units"].sum())


def is_available() -> bool:
    return _csv_path() is not None
