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


def find_committed_nger() -> Path | None:
    """Look for a committed NGER spreadsheet in data/. Returns the path of the
    first match, preferring filenames with the latest year. Returns None if
    no candidate found."""
    if not DATA_DIR.exists():
        return None
    candidates = []
    for p in DATA_DIR.iterdir():
        n = p.name.lower()
        if not p.is_file():
            continue
        if not (n.endswith(".xlsx") or n.endswith(".xls")):
            continue
        if "nger" in n or "corporate-emissions" in n or "corporate_emissions" in n:
            candidates.append(p)
    if not candidates:
        return None
    # Prefer newest by filename year token, then mtime
    def year_key(p: Path) -> int:
        m = re.search(r"(20\d{2})", p.name)
        return int(m.group(1)) if m else 0
    candidates.sort(key=lambda p: (year_key(p), p.stat().st_mtime), reverse=True)
    return candidates[0]


def infer_year_from_filename(path: Path) -> int | None:
    """Extract a 4-digit year from a NGER filename (e.g. '2024-25', '2025')."""
    m = re.findall(r"20\d{2}", path.name)
    if not m:
        return None
    # Filename like '2024-25' → return the higher year (FY end)
    return max(int(y) for y in m)


HEADER_ALIASES = {
    "reporting_entity": [
        "organisation name", "organization name",
        "reporting entity name", "reporting entity", "controlling corporation",
        "controlling corporation name", "corporate group name", "company name",
        "registered corporation", "entity name",
    ],
    "abn": ["abn", "identifying details", "abn or acn", "acn"],
    "scope1": [
        "total scope 1 emissions (t co2-e)", "total scope 1 emissions",
        "scope 1 emissions (t co2-e)", "scope 1 emissions", "scope 1 (t co2-e)",
        "scope 1 emissions in tco2-e", "total scope 1 (t co2-e)",
        "scope 1 (tco2e)",
    ],
    "scope2": [
        "total scope 2 emissions (t co2-e)", "total scope 2 emissions",
        "scope 2 emissions (t co2-e)", "scope 2 emissions",
        "scope 2 (t co2-e)", "scope 2 emissions in tco2-e",
        "scope 2 location-based emissions (t co2-e)",
        "scope 2 (tco2e)",
    ],
    "energy": [
        "net energy consumed (gj)",
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
        # Try header at row 0..6 (CER often has title rows above the header)
        for hdr in (0, 1, 2, 3, 4, 5, 6):
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
            # Sanity check: Scope 1 and Scope 2 must come from DIFFERENT source columns,
            # and neither should equal the Reporting Entity source. Otherwise the matcher
            # has latched onto a single long-text cell (disclaimer / title) by substring.
            non_null_sources = [v for v in mapping.values() if v]
            if len(non_null_sources) != len(set(non_null_sources)):
                continue  # at least two canonicals share a source column → not a real header
            # Need Reporting Entity + Scope 1 + Scope 2
            if mapping["Reporting Entity"] and mapping["Scope 1 (tCO2e)"] and mapping["Scope 2 (tCO2e)"]:
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
    "corporation", "corp", "plc", "the", "australia", "australian",
    "new", "zealand", "(asx listed)", "and", "&",
)


def _name_key(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    for tok in _STRIP_TOKENS:
        n = re.sub(rf"\b{re.escape(tok)}\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def match_to_cohort(nger: pd.DataFrame, cohort_names: list[str]) -> dict[str, str]:
    """For each cohort company, find the best-matching NGER reporter.
    Returns a dict mapping cohort name → NGER reporting entity name.

    Algorithm:
      1. Exact normalised-key match.
      2. Token-overlap with ≥2 shared tokens (handles multi-word names robustly).
      3. First-token equality: cohort first token == NGER first token AND
         that first token isn't shared by multiple unrelated NGER reporters
         (avoids 'national' / 'new' / 'australian' false matches).
    """
    nger_pairs = [(_name_key(name), name) for name in nger["Reporting Entity"] if _name_key(name)]
    nger_keys = dict(nger_pairs)

    # Frequency of each first token across NGER (for first-token uniqueness)
    from collections import Counter
    first_token_count: Counter = Counter(nk.split()[0] for nk, _ in nger_pairs if nk.split())

    matches: dict[str, str] = {}
    for cohort in cohort_names:
        ck = _name_key(cohort)
        if not ck:
            continue
        ck_tokens = ck.split()
        if not ck_tokens:
            continue

        # 1. Exact key
        if ck in nger_keys:
            matches[cohort] = nger_keys[ck]
            continue

        # 2. Token-overlap (best score wins, requires ≥2 shared tokens OR
        #    ≥1 shared and the cohort/NGER side has ≤2 tokens total)
        best, best_score = None, 0.0
        ck_set = set(ck_tokens)
        for nk, nname in nger_pairs:
            nk_set = set(nk.split())
            shared = ck_set & nk_set
            if not shared:
                continue
            shorter_size = min(len(ck_set), len(nk_set))
            if shorter_size == 0:
                continue
            score = len(shared) / shorter_size
            min_shared = 2 if shorter_size >= 3 else 1
            if len(shared) >= min_shared and score > best_score:
                best, best_score = nname, score
        if best and best_score >= 0.6:
            matches[cohort] = best
            continue
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


# ─── NGER-only cohort ─────────────────────────────────────────────────────────

def build_nger_only_cohort(existing_cohort_names: list[str]) -> pd.DataFrame:
    """Return a phase1-shape DataFrame of NGER reporters who are NOT already
    in another cohort. Used as Cohort 4 in the unified view.

    Each row carries the company name, NGER ABN, Scope 1+2, energy, and
    placeholder target columns (since we don't know targets for these). The
    BD signal is 'large emitter, status unknown — research before outreach'.
    """
    p = find_committed_nger()
    if p is None:
        return pd.DataFrame()
    try:
        nger = load_nger(p)
    except Exception:
        return pd.DataFrame()
    if nger.empty:
        return nger

    # Find which NGER reporters are already represented in the other cohorts.
    matches = match_to_cohort(nger, existing_cohort_names)
    matched_nger_entities = set(matches.values())

    nger_only = nger[~nger["Reporting Entity"].isin(matched_nger_entities)].copy()
    if nger_only.empty:
        return nger_only

    # Drop placeholder rows (NaN data) just in case
    nger_only = nger_only[
        nger_only["Scope 1 (tCO2e)"].notna() | nger_only["Scope 2 (tCO2e)"].notna()
    ].reset_index(drop=True)

    # Title-case the entity name for nicer display
    nger_only["Reporting Entity"] = nger_only["Reporting Entity"].astype(str).str.title()

    out = pd.DataFrame()
    out["Company Name"] = nger_only["Reporting Entity"]
    out["ISIN"] = ""
    out["Country"] = "Australia"
    out["Region"] = "Oceania"
    out["Sector"] = "NGER reporter (sector unclassified)"
    out["Industry"] = ""
    out["Organization Type"] = "NGER reporter"
    out["Near-term Status"] = ""
    out["Long-term Status"] = ""
    out["Net-Zero Status"] = ""
    out["Target"] = ""
    out["Target Year"] = pd.NA
    out["Long-term Target Year"] = pd.NA
    out["Net-Zero Year"] = pd.NA
    out["Target Classification"] = "Not assessed (NGER reporter)"
    out["Target Classification (Long)"] = "Not assessed (NGER reporter)"
    out["BA1.5 Status"] = ""
    out["BA1.5 Date"] = ""
    out["Removal/Extension Reason"] = ""
    out["Date Committed"] = pd.NA
    out["Date Published"] = pd.NA
    out["Date Updated"] = pd.NA
    out["SBTi ID"] = ""
    out["LEI"] = ""
    out["Base Year"] = pd.NA
    out["Ambition"] = ""

    # NGER-specific extras
    out["ABN"] = nger_only["ABN"]
    out["NGER Scope 1 (tCO2e)"] = nger_only["Scope 1 (tCO2e)"]
    out["NGER Scope 2 (tCO2e)"] = nger_only["Scope 2 (tCO2e)"]
    out["NGER Total Energy (GJ)"] = nger_only["Total Energy (GJ)"]

    # Sort by Scope 1 descending (biggest emitters first — strongest BD signal)
    out = out.sort_values("NGER Scope 1 (tCO2e)", ascending=False, na_position="last").reset_index(drop=True)

    # Compute ASRS Tier — NGER threshold (>50 ktCO2e Scope 1+2 OR >200 TJ) implies
    # the entity is large enough to be Tier 1 by emissions; without revenue data
    # we can't verify the financial thresholds, so mark as Tier 1 (NGER proxy).
    out["ASRS Tier"] = "Tier 1 (NGER proxy)"

    return out
