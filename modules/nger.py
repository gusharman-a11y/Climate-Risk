"""NGER (National Greenhouse and Energy Reporting) ingestion.

Australian Clean Energy Regulator publishes annual corporate-level emissions
and energy data under the NGER scheme. Coverage threshold: >50 ktCO2e
Scope 1+2 OR >200 TJ energy. Captures virtually every material Australian
emitter.

Source: https://cer.gov.au/markets/reports-and-data/nger-reporting-data-and-registers/

Columns vary slightly year-to-year. This module is tolerant — it inspects
the header row, matches common variants, and standardises to:
  - "Reporting Entity"
  - "ABN"
  - "Scope 1 (tCO2e)"
  - "Scope 2 (tCO2e)"   — location-based by default
  - "Total Energy (GJ)"
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

HEADER_ALIASES = {
    "reporting_entity": [
        "reporting entity name", "reporting entity", "controlling corporation",
        "controlling corporation name", "corporate group name", "company name",
        "registered corporation", "name", "entity name",
    ],
    "abn": ["abn"],
    "scope1": [
        "total scope 1 emissions (t co2-e)", "total scope 1 emissions",
        "scope 1 emissions (t co2-e)", "scope 1 emissions", "scope 1 (t co2-e)",
        "scope 1 emissions in tco2-e", "total scope 1 (t co2-e)",
        "scope 1 (tco2e)", "scope 1",
    ],
    "scope2": [
        "total scope 2 emissions (t co2-e)", "total scope 2 emissions",
        "scope 2 emissions (t co2-e)", "scope 2 emissions",
        "scope 2 (t co2-e)", "scope 2 emissions in tco2-e",
        "scope 2 location-based emissions (t co2-e)",
        "scope 2 (tco2e)", "scope 2",
    ],
    "energy": [
        "total net energy consumption (gj)", "total net energy consumption",
        "net energy consumption (gj)", "energy consumption (gj)",
        "total energy (gj)", "total energy consumed (gj)",
    ],
}


def _normalise_header(h: str) -> str:
    return re.sub(r"\s+", " ", str(h)).strip().lower()


def _match_column(headers: list[str], aliases: list[str]) -> str | None:
    norm_headers = {_normalise_header(h): h for h in headers}
    for alias in aliases:
        if alias in norm_headers:
            return norm_headers[alias]
    # Substring fallback — e.g. column has extra qualifier
    for alias in aliases:
        for nh, original in norm_headers.items():
            if alias in nh:
                return original
    return None


def load_nger(file: io.BytesIO | Path | bytes) -> pd.DataFrame:
    """Load the NGER corporate emissions and energy spreadsheet.

    Tries each sheet in turn and picks the first one with the required
    columns (Reporting Entity + Scope 1 + Scope 2). Returns a standardised
    DataFrame with the canonical column names.
    """
    if isinstance(file, bytes):
        file = io.BytesIO(file)
    if isinstance(file, Path):
        xls = pd.ExcelFile(file)
    else:
        # Streamlit upload object or BytesIO
        try:
            data = file.getvalue() if hasattr(file, "getvalue") else file.read()
        except Exception:
            data = file
        xls = pd.ExcelFile(io.BytesIO(data))

    best_df: pd.DataFrame | None = None
    best_mapping: dict[str, str] = {}

    for sheet in xls.sheet_names:
        # Try header at row 0, 1, 2 (CER often has title rows above the header)
        for hdr in (0, 1, 2, 3):
            try:
                df = pd.read_excel(xls, sheet_name=sheet, header=hdr)
            except Exception:
                continue
            if df.empty:
                continue
            mapping = {
                "Reporting Entity": _match_column(df.columns.tolist(), HEADER_ALIASES["reporting_entity"]),
                "ABN": _match_column(df.columns.tolist(), HEADER_ALIASES["abn"]),
                "Scope 1 (tCO2e)": _match_column(df.columns.tolist(), HEADER_ALIASES["scope1"]),
                "Scope 2 (tCO2e)": _match_column(df.columns.tolist(), HEADER_ALIASES["scope2"]),
                "Total Energy (GJ)": _match_column(df.columns.tolist(), HEADER_ALIASES["energy"]),
            }
            # Need Reporting Entity + at least one of Scope 1 / Scope 2
            if mapping["Reporting Entity"] and (mapping["Scope 1 (tCO2e)"] or mapping["Scope 2 (tCO2e)"]):
                best_df = df
                best_mapping = mapping
                break
        if best_df is not None:
            break

    if best_df is None:
        raise ValueError(
            "Could not detect NGER columns. Expected at least 'Reporting Entity' "
            "and one of 'Scope 1' / 'Scope 2'. Got: "
            + ", ".join(str(c) for c in (xls.sheet_names[:3] if xls.sheet_names else []))
        )

    out = pd.DataFrame()
    for canon, src in best_mapping.items():
        if src is not None and src in best_df.columns:
            out[canon] = best_df[src]
        else:
            out[canon] = pd.NA

    # Drop rows with no entity name and coerce numerics
    out = out[out["Reporting Entity"].notna()].reset_index(drop=True)
    for col in ("Scope 1 (tCO2e)", "Scope 2 (tCO2e)", "Total Energy (GJ)"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["Reporting Entity"] = out["Reporting Entity"].astype(str).str.strip()
    return out


# ─── Match NGER reporters to our cohort by company name ──────────────────────

_STRIP_TOKENS = (
    "limited", "ltd", "pty", "group holdings", "holdings", "group",
    "corporation", "corp", "plc", "the ", "australia", "(asx listed)",
    "and", "&",
)


def _name_key(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    for tok in _STRIP_TOKENS:
        n = re.sub(rf"\b{re.escape(tok)}\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def match_to_cohort(nger: pd.DataFrame, cohort_names: list[str]) -> dict[str, str]:
    """For each cohort company, find the best-matching NGER reporter.
    Returns a dict mapping cohort name → NGER reporting entity name."""
    nger_keys = {_name_key(name): name for name in nger["Reporting Entity"]}
    matches: dict[str, str] = {}
    for cohort in cohort_names:
        ck = _name_key(cohort)
        if not ck:
            continue
        # Exact key match
        if ck in nger_keys:
            matches[cohort] = nger_keys[ck]
            continue
        # Substring either way
        for nk, nname in nger_keys.items():
            if not nk:
                continue
            if ck in nk or nk in ck:
                matches[cohort] = nname
                break
        else:
            # First-token match (e.g. 'bhp' matches 'bhp billiton ltd')
            ck_first = ck.split()[0] if ck else ""
            for nk, nname in nger_keys.items():
                if ck_first and nk.split() and nk.split()[0] == ck_first:
                    matches[cohort] = nname
                    break
    return matches


def inject_to_cache(
    nger: pd.DataFrame,
    cohort_names: list[str],
    cache: dict,
    reporting_year: int,
    isin_lookup: dict[str, str] | None = None,
) -> tuple[int, list[str]]:
    """Populate the emissions cache with NGER-derived Scope 1+2 figures for
    matched companies. Returns (rows_ingested, unmatched_cohort_names)."""
    isin_lookup = isin_lookup or {}
    matches = match_to_cohort(nger, cohort_names)
    nger_indexed = nger.set_index("Reporting Entity")

    ingested = 0
    for cohort, nger_name in matches.items():
        try:
            row = nger_indexed.loc[nger_name]
        except KeyError:
            continue
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        s1 = row.get("Scope 1 (tCO2e)")
        s2 = row.get("Scope 2 (tCO2e)")
        if pd.isna(s1) and pd.isna(s2):
            continue
        key = isin_lookup.get(cohort, "").upper().strip() or cohort
        rec = cache.get(key, {"company": cohort, "isin": isin_lookup.get(cohort, ""), "history": []})
        rec["history"] = [h for h in rec["history"] if h.get("year") != reporting_year]
        rec["history"].append({
            "year": int(reporting_year),
            "s1": float(s1) if pd.notna(s1) else None,
            "s2": float(s2) if pd.notna(s2) else None,
            "s3": None,
            "source": "nger",
            "source_url": "https://cer.gov.au/markets/reports-and-data/nger-reporting-data-and-registers/",
            "nger_entity": nger_name,
        })
        cache[key] = rec
        ingested += 1

    unmatched = [c for c in cohort_names if c not in matches]
    return ingested, unmatched
