"""Phase 2 — Delivery / trajectory analysis.

For each company in the Phase 1 ASX SBTi cohort, compare reported emissions
against the linear path implied by their committed target. Output: gap-to-path
in percentage points (positive = ahead of path).

Emissions data layers (in priority order):
  1. Auto-scraped from the latest sustainability report (modules/scraper.py)
  2. CSV merged via the sidebar uploader (data/emissions.csv schema)
  3. Manual entry through the company drill-down form

Whichever layer populates a company's record, the math is the same.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from modules.sbti import CANON, DATA_DIR

EMISSIONS_CACHE = DATA_DIR / "emissions_cache.json"
EMISSIONS_CSV = DATA_DIR / "emissions.csv"

CSV_TEMPLATE_COLS = [
    "Company Name", "ISIN", "Reporting Year",
    "Scope 1 (tCO2e)", "Scope 2 (tCO2e)", "Scope 3 (tCO2e)",
    "Base Year", "Base Year Scope 1+2 (tCO2e)", "Base Year Scope 3 (tCO2e)",
    "Source",  # "scraper" / "csv" / "manual"
    "Source URL",
]


# ─── Target-language parser ──────────────────────────────────────────────────

@dataclass
class TargetParams:
    base_year: int | None
    target_year: int | None
    ambition_pct: float | None  # near-term S1+S2 ambition as a percentage (e.g. 50.0 for 50%)
    raw: str = ""


def parse_target_params(target_text: str | None, near_term_year: int | None = None) -> TargetParams:
    """Pull base year, target year, and headline near-term ambition % from
    SBTi target wording. Falls back to the structured `near_term_target_year`
    column where the wording doesn't include a year."""
    if not target_text or pd.isna(target_text):
        return TargetParams(None, near_term_year, None, "")
    t = str(target_text)

    # Base year — "from a 2019 base year" / "from a 2018 base-year" / "compared to 2020"
    m_base = re.search(r"from\s+a?\s*(19|20)\d{2}\s*base", t, re.I)
    base_year: int | None = None
    if m_base:
        base_year = int(re.search(r"(19|20)\d{2}", m_base.group(0)).group(0))
    else:
        m_alt = re.search(r"\b(?:vs\.?|versus|compared to|against)\s*(?:a\s+)?((?:19|20)\d{2})", t, re.I)
        if m_alt:
            base_year = int(m_alt.group(1))

    # Target year — "by 2030" / "by 20XX"
    m_tgt = re.search(r"by\s+((?:19|20)\d{2})", t, re.I)
    target_year = int(m_tgt.group(1)) if m_tgt else near_term_year

    # Near-term ambition % — first percentage near "scope 1" or "scope 1 and 2"
    # SBTi targets are typically phrased as "reduce absolute scope 1 and 2 GHG emissions X%"
    pct: float | None = None
    m_pct = re.search(
        r"scope\s*1[^%]{0,60}?(\d{1,3}(?:\.\d+)?)\s*%",
        t, re.I,
    )
    if m_pct:
        pct = float(m_pct.group(1))
    else:
        # Fallback: first percentage in the text
        m_any = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", t)
        if m_any:
            pct = float(m_any.group(1))

    return TargetParams(base_year, target_year, pct, t)


# ─── Trajectory math ─────────────────────────────────────────────────────────

@dataclass
class GapResult:
    required_pct: float | None         # required reduction at latest reporting year (pp)
    actual_pct: float | None           # actual reduction achieved at latest reporting year (pp)
    gap_pct: float | None              # actual − required (positive = ahead of path)
    delivery: str                      # "Green" / "Amber" / "Red" / "N/A"
    note: str = ""


def delivery_band(gap_pct: float | None) -> str:
    if gap_pct is None:
        return "N/A"
    if gap_pct >= 0:
        return "Green"
    if gap_pct >= -10:
        return "Amber"
    return "Red"


def compute_gap(
    base_year: int | None,
    base_s12: float | None,
    target_year: int | None,
    ambition_pct: float | None,
    latest_year: int | None,
    latest_s12: float | None,
) -> GapResult:
    """All inputs are S1+S2 absolute emissions for the headline near-term target.
    Returns required/actual/gap reductions at `latest_year` in percentage points."""
    if any(v is None for v in (base_year, base_s12, target_year, ambition_pct, latest_year, latest_s12)):
        return GapResult(None, None, None, "N/A", "Missing inputs (need base year, base S1+S2, target year, ambition, latest year, latest S1+S2).")
    if target_year <= base_year:
        return GapResult(None, None, None, "N/A", "Target year must be after base year.")
    if base_s12 <= 0:
        return GapResult(None, None, None, "N/A", "Base year S1+S2 must be > 0.")
    if latest_year < base_year:
        return GapResult(None, None, None, "N/A", "Latest reporting year is before base year.")

    elapsed = latest_year - base_year
    horizon = target_year - base_year
    required_pct = (elapsed / horizon) * ambition_pct if horizon else None

    actual_pct = (1 - latest_s12 / base_s12) * 100
    gap_pct = actual_pct - required_pct
    return GapResult(required_pct, actual_pct, gap_pct, delivery_band(gap_pct))


# ─── Emissions cache (manual entries + scraper results) ──────────────────────

def load_cache() -> dict:
    if EMISSIONS_CACHE.exists():
        try:
            return json.loads(EMISSIONS_CACHE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    EMISSIONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    EMISSIONS_CACHE.write_text(json.dumps(cache, indent=2, default=str))


def upsert_record(
    cache: dict,
    company: str,
    isin: str | None,
    *,
    reporting_year: int,
    s1: float | None,
    s2: float | None,
    s3: float | None,
    base_year: int | None = None,
    base_s12: float | None = None,
    base_s3: float | None = None,
    source: str = "manual",
    source_url: str = "",
) -> None:
    key = (isin or "").strip().upper() or company.strip()
    rec = cache.get(key, {"company": company, "isin": isin or "", "history": []})
    # Replace any record for the same year + scope combination with the new one
    rec["history"] = [h for h in rec["history"] if h.get("year") != reporting_year]
    rec["history"].append({
        "year": int(reporting_year),
        "s1": s1, "s2": s2, "s3": s3,
        "source": source, "source_url": source_url,
    })
    if base_year is not None:
        rec["base_year"] = int(base_year)
    if base_s12 is not None:
        rec["base_s12"] = float(base_s12)
    if base_s3 is not None:
        rec["base_s3"] = float(base_s3)
    cache[key] = rec


def merge_csv(cache: dict, csv_bytes: bytes) -> int:
    """Merge an uploaded emissions CSV into the cache. Returns rows ingested."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    df.columns = [c.strip() for c in df.columns]
    needed = {"Company Name", "Reporting Year"}
    if not needed.issubset(df.columns):
        raise ValueError(f"CSV missing required columns. Need at least: {needed}.")
    rows = 0
    for _, r in df.iterrows():
        try:
            upsert_record(
                cache,
                company=str(r["Company Name"]).strip(),
                isin=str(r.get("ISIN", "")).strip(),
                reporting_year=int(r["Reporting Year"]),
                s1=_num(r.get("Scope 1 (tCO2e)")),
                s2=_num(r.get("Scope 2 (tCO2e)")),
                s3=_num(r.get("Scope 3 (tCO2e)")),
                base_year=_int(r.get("Base Year")),
                base_s12=_num(r.get("Base Year Scope 1+2 (tCO2e)")),
                base_s3=_num(r.get("Base Year Scope 3 (tCO2e)")),
                source=str(r.get("Source", "csv")).strip() or "csv",
                source_url=str(r.get("Source URL", "")).strip(),
            )
            rows += 1
        except (ValueError, TypeError):
            continue
    return rows


def _num(v) -> float | None:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v) -> int | None:
    try:
        if v is None or pd.isna(v):
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


# ─── Per-row gap computation against the cache ───────────────────────────────

def latest_record(rec: dict) -> dict | None:
    if not rec or not rec.get("history"):
        return None
    return max(rec["history"], key=lambda h: h.get("year", 0))


def assess_delivery(row: pd.Series, cache: dict) -> dict:
    """Return delivery columns for one Phase 1 row."""
    isin = str(row.get(CANON["isin"], "")).strip().upper()
    company = str(row.get(CANON["company"], "")).strip()
    rec = cache.get(isin) or cache.get(company)

    target_text = row.get(CANON["target"])
    near_term_year = _int(row.get(CANON["target_year"]))
    params = parse_target_params(target_text, near_term_year)

    base_year = (rec or {}).get("base_year") or params.base_year
    base_s12 = (rec or {}).get("base_s12")
    latest = latest_record(rec)
    latest_year = latest["year"] if latest else None
    latest_s12 = None
    if latest:
        s1 = latest.get("s1") or 0
        s2 = latest.get("s2") or 0
        latest_s12 = s1 + s2 if (latest.get("s1") is not None or latest.get("s2") is not None) else None

    gap = compute_gap(
        base_year=base_year,
        base_s12=base_s12,
        target_year=params.target_year,
        ambition_pct=params.ambition_pct,
        latest_year=latest_year,
        latest_s12=latest_s12,
    )

    return {
        "Latest Reported Year": latest_year if latest_year else pd.NA,
        "Latest S1+S2 (tCO2e)": latest_s12 if latest_s12 is not None else pd.NA,
        "Base Year (used)": base_year if base_year else pd.NA,
        "Base S1+S2 (tCO2e)": base_s12 if base_s12 is not None else pd.NA,
        "Ambition % (parsed)": params.ambition_pct if params.ambition_pct else pd.NA,
        "Required Reduction % (now)": round(gap.required_pct, 1) if gap.required_pct is not None else pd.NA,
        "Actual Reduction % (now)": round(gap.actual_pct, 1) if gap.actual_pct is not None else pd.NA,
        "Gap to Path (pp)": round(gap.gap_pct, 1) if gap.gap_pct is not None else pd.NA,
        "Delivery RAG": gap.delivery,
        "Delivery Note": gap.note,
        "Data Source": (latest or {}).get("source", "—") if latest else "—",
    }


def build_delivery(screen: pd.DataFrame, cache: dict) -> pd.DataFrame:
    if screen.empty:
        return screen
    extra = screen.apply(lambda r: assess_delivery(r, cache), axis=1, result_type="expand")
    return pd.concat([screen.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)


DELIVERY_COLOUR = {
    "Green": "#16A34A",
    "Amber": "#D97706",
    "Red": "#DC2626",
    "N/A": "#6B7280",
}


def csv_template_bytes() -> bytes:
    df = pd.DataFrame(columns=CSV_TEMPLATE_COLS)
    return df.to_csv(index=False).encode("utf-8")
