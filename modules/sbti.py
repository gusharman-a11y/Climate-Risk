"""SBTi company tracker: data loading, normalisation, and composite RAG scoring."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ASEAN_AU_NZ_JP = {
    "Australia", "New Zealand", "Japan",
    "Brunei Darussalam", "Brunei", "Cambodia", "Indonesia",
    "Lao People's Democratic Republic", "Laos", "Lao PDR",
    "Malaysia", "Myanmar", "Philippines", "Singapore", "Thailand",
    "Viet Nam", "Vietnam",
}

# Canonical column names the rest of the app expects.
CANON = {
    "sbti_id": "SBTi ID",
    "company": "Company Name",
    "isin": "ISIN",
    "lei": "LEI",
    "country": "Country",
    "region": "Region",
    "sector": "Sector",
    "industry": "Industry",
    "org_type": "Organization Type",
    "target": "Target",
    "target_class": "Target Classification",
    "target_class_long": "Target Classification (Long)",
    "target_year": "Target Year",
    "base_year": "Base Year",
    "near_term_status": "Near-term Status",
    "long_term_status": "Long-term Status",
    "long_term_target_class": "Long-term Target Classification",
    "long_term_target_year": "Long-term Target Year",
    "net_zero_status": "Net-Zero Status",
    "net_zero_year": "Net-Zero Year",
    "ba15_status": "BA1.5 Status",
    "ba15_date": "BA1.5 Date",
    "ambition": "Ambition",
    "removal_reason": "Removal/Extension Reason",
    "date_committed": "Date Committed",
    "date_published": "Date Published",
    "date_updated": "Date Updated",
}

# Common header variants seen in SBTi exports → canonical name.
# Keys are lowercased with underscores/hyphens collapsed to single spaces.
ALIASES = {
    "sbti id": "sbti_id",
    "company name": "company",
    "company": "company",
    "isin": "isin",
    "lei": "lei",
    "location": "country",
    "country": "country",
    "region": "region",
    "sector": "sector",
    "primary sector": "sector",
    "industry": "industry",
    "primary sub sector": "industry",
    "organization type": "org_type",
    "company classification": "org_type",
    "full target language": "target",
    "target wording": "target",
    "target": "target",
    "target classification": "target_class",
    "target classification short": "target_class",
    "near term target classification": "target_class",
    "target classification long": "target_class_long",
    "long term target classification": "long_term_target_class",
    "near term target year": "target_year",
    "target year": "target_year",
    "near term base year": "base_year",
    "base year": "base_year",
    "near term status": "near_term_status",
    "near term target status": "near_term_status",
    "status": "near_term_status",
    "long term status": "long_term_status",
    "long term target year": "long_term_target_year",
    "net zero status": "net_zero_status",
    "net zero year": "net_zero_year",
    "ba15 status": "ba15_status",
    "ba1.5 status": "ba15_status",
    "ba15 date": "ba15_date",
    "ba1.5 date": "ba15_date",
    "ambition": "ambition",
    "near term ambition": "ambition",
    "reason for extension or removal": "removal_reason",
    "removal reason": "removal_reason",
    "date committed": "date_committed",
    "target submitted to sbti": "date_committed",
    "date published": "date_published",
    "date updated": "date_updated",
    "date update": "date_updated",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = str(col).strip().lower().replace("_", " ").replace("-", " ")
        key = re.sub(r"\s+", " ", key).strip()
        if key in ALIASES:
            rename[col] = CANON[ALIASES[key]]
    df = df.rename(columns=rename)
    for canon_col in CANON.values():
        if canon_col not in df.columns:
            df[canon_col] = pd.NA
    return df


def load_sbti(file: Path | io.BytesIO | None = None) -> pd.DataFrame:
    """Load the SBTi Companies-Taking-Action dataset.

    Accepts an uploaded file, an explicit Path, or falls back to data/sbti_companies.{csv,xlsx}.
    """
    if file is None:
        for name in ("sbti_companies.csv", "sbti_companies.xlsx"):
            p = DATA_DIR / name
            if p.exists() and p.stat().st_size > 1024:
                file = p
                break
    if file is None:
        return pd.DataFrame(columns=list(CANON.values()))

    if isinstance(file, Path):
        df = pd.read_excel(file) if file.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(file)
    else:
        name = getattr(file, "name", "").lower()
        df = pd.read_excel(file) if name.endswith((".xlsx", ".xls")) else pd.read_csv(file)

    df = _normalise_columns(df)
    df[CANON["company"]] = df[CANON["company"]].astype(str).str.strip()
    return df


# ── ASRS tiering ───────────────────────────────────────────────────────────────
# Corporations Amendment (Sustainability Reporting) Act 2024.
# ≥2 of 3 thresholds must be met for each group.
# Group 1: revenue ≥ $500M | assets ≥ $1B   | employees ≥ 500  (from 1 Jan 2025)
# Group 2: revenue ≥ $200M | assets ≥ $500M | employees ≥ 500  (from 1 Jul 2026)
# Group 3: revenue ≥ $50M  | assets ≥ $25M  | employees ≥ 100  (from 1 Jul 2027)


@dataclass
class AsrsThresholds:
    revenue_aud: float
    assets_aud: float
    employees: int


GROUP_1 = AsrsThresholds(500_000_000, 1_000_000_000, 500)
GROUP_2 = AsrsThresholds(200_000_000, 500_000_000, 250)   # s292A Corporations Act: 250 employees
GROUP_3 = AsrsThresholds(50_000_000, 25_000_000, 100)     # new — mandatory from 1 Jul 2027


def _meets(row: pd.Series, t: AsrsThresholds) -> bool:
    hits = 0
    if row.get("Revenue (AUD)", 0) >= t.revenue_aud:
        hits += 1
    if row.get("Assets (AUD)", 0) >= t.assets_aud:
        hits += 1
    if row.get("Employees", 0) >= t.employees:
        hits += 1
    return hits >= 2


def asrs_tier(row: pd.Series) -> str:
    """Return AASB S2 / ASRS reporting tier: 'Tier 1', 'Tier 2', 'Tier 3',
    or 'Unclassified'. Kept for backward compatibility — new code should use
    modules.asrs.asrs_group() which returns 'Group N' labels with correct
    mandatory dates. This function mirrors that logic but returns 'Tier N'."""
    if _meets(row, GROUP_1):
        return "Tier 1"
    if _meets(row, GROUP_2):
        return "Tier 2"
    if _meets(row, GROUP_3):
        return "Tier 3"
    # Proxy from Market Cap Tier (ASX 200 cohort)
    mc = str(row.get("Market Cap Tier", "")).strip().lower()
    if mc in ("mega", "large"):
        return "Tier 1"
    if mc == "mid":
        return "Tier 2"
    if mc in ("small", "micro"):
        return "Tier 3"
    # Proxy from organisation type + ISIN
    org = str(row.get(CANON["org_type"], "")).lower()
    if "sme" in org:
        return "Tier 3"
    if "corporate" in org or "company" in org or "financial" in org:
        isin = str(row.get(CANON["isin"], "")).strip().upper()
        if isin.startswith("AU"):
            return "Tier 1"
        return "Tier 2"
    return "Unclassified"


def attach_size_data(sbti: pd.DataFrame, size_file: Path | io.BytesIO | None) -> pd.DataFrame:
    """Merge optional revenue/assets/employee data by Company Name."""
    out = sbti.copy()
    for col in ("Revenue (AUD)", "Assets (AUD)", "Employees"):
        if col not in out.columns:
            out[col] = 0
    if size_file is not None:
        if isinstance(size_file, Path):
            size_df = pd.read_csv(size_file) if size_file.suffix == ".csv" else pd.read_excel(size_file)
        else:
            name = getattr(size_file, "name", "").lower()
            size_df = pd.read_csv(size_file) if name.endswith(".csv") else pd.read_excel(size_file)
        size_df.columns = [c.strip() for c in size_df.columns]
        if "Company Name" in size_df.columns:
            out = out.drop(columns=["Revenue (AUD)", "Assets (AUD)", "Employees"], errors="ignore")
            out = out.merge(size_df, on="Company Name", how="left")
            for col in ("Revenue (AUD)", "Assets (AUD)", "Employees"):
                if col not in out.columns:
                    out[col] = 0
                out[col] = out[col].fillna(0)
    out["ASRS Tier"] = out.apply(asrs_tier, axis=1)
    return out


# ── Composite RAG scoring ──────────────────────────────────────────────────────

STATUS_POINTS = {
    "targets set": 3, "validated": 3, "approved": 3,
    "committed": 1,
    "expired": 0, "removed": -2, "commitment removed": -2,
}

AMBITION_POINTS = {
    "1.5": 3, "1.5°c": 3, "1.5c": 3,
    "well-below 2": 1, "wb2": 1, "well below 2": 1,
    "2°c": 0, "2c": 0,
}


def _to_int(v) -> int | None:
    try:
        i = int(float(v))
        return i if i > 1900 else None
    except Exception:
        return None


def _status_score(value: str) -> int:
    v = value.strip().lower()
    if not v or v == "nan":
        return 0
    if "removed" in v:
        return -2
    if "expired" in v:
        return -1
    if "targets set" in v or "validated" in v or "approved" in v:
        return 3
    if "committed" in v:
        return 1
    return 0


def _score_row(row: pd.Series) -> dict:
    near_term = str(row.get(CANON["near_term_status"], ""))
    long_term = str(row.get(CANON["long_term_status"], ""))
    nz_status = str(row.get(CANON["net_zero_status"], ""))
    ambition_long = str(row.get(CANON["target_class_long"], ""))
    ambition_short = str(row.get(CANON["target_class"], ""))
    ambition_field = str(row.get(CANON["ambition"], ""))
    removal_reason = str(row.get(CANON["removal_reason"], "")).strip()

    target_year = _to_int(row.get(CANON["target_year"]))
    nz_year = _to_int(row.get(CANON["net_zero_year"])) or _to_int(row.get(CANON["long_term_target_year"]))

    # 1. Near-term status (−2..3)
    status_pts = _status_score(near_term)

    # 2. Ambition — combine all three classification fields, take best (0..3)
    ambition_blob = " ".join([ambition_long, ambition_short, ambition_field]).lower()
    ambition_pts = 0
    for key, pts in AMBITION_POINTS.items():
        if key in ambition_blob:
            ambition_pts = max(ambition_pts, pts)

    # 3. Net-zero commitment (0..2): year set + status validated
    nz_pts = 0
    if nz_year:
        nz_pts += 1
    nz_status_pts = _status_score(nz_status)
    lt_status_pts = _status_score(long_term)
    if max(nz_status_pts, lt_status_pts) >= 3:
        nz_pts += 1

    # 4. Expired/removed penalty (−2..0)
    this_year = datetime.utcnow().year
    expired_pts = 0
    if removal_reason and removal_reason.lower() not in {"nan", "none", ""}:
        expired_pts = -2
    elif target_year and target_year < this_year and "targets set" not in near_term.lower():
        expired_pts = -2

    # 5. Disclosure recency (0..2) — prefer date_updated, then published, then committed
    rec_pts = 0
    for col in (CANON["date_updated"], CANON["date_published"], CANON["date_committed"], CANON["ba15_date"]):
        d = pd.to_datetime(row.get(col), errors="coerce")
        if pd.notna(d):
            age = (datetime.utcnow() - d.to_pydatetime()).days / 365.25
            rec_pts = max(rec_pts, 2 if age <= 1 else 1 if age <= 3 else 0)

    total = status_pts + ambition_pts + nz_pts + expired_pts + rec_pts

    if total >= 7:
        rag = "Green"
    elif total >= 4:
        rag = "Amber"
    elif total >= 1:
        rag = "Red"
    else:
        rag = "Off Track"

    return {
        "Status pts": status_pts,
        "Ambition pts": ambition_pts,
        "Net-Zero pts": nz_pts,
        "Expired pts": expired_pts,
        "Recency pts": rec_pts,
        "Composite Score": total,
        "RAG": rag,
    }


def score(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.assign(**{k: pd.Series(dtype="float64") for k in
                            ["Status pts", "Ambition pts", "Net-Zero pts", "Expired pts",
                             "Recency pts", "Composite Score", "RAG"]})
    scored = df.apply(_score_row, axis=1, result_type="expand")
    return pd.concat([df.reset_index(drop=True), scored.reset_index(drop=True)], axis=1)


RAG_COLOUR = {
    "Green": "#16A34A",
    "Amber": "#D97706",
    "Red": "#DC2626",
    "Off Track": "#7F1D1D",
}


# ── CDP scores (optional public CSV) ──────────────────────────────────────────

def attach_cdp(df: pd.DataFrame, cdp_file: Path | io.BytesIO | None) -> pd.DataFrame:
    if cdp_file is None:
        if "CDP Score" not in df.columns:
            df["CDP Score"] = pd.NA
        return df
    if isinstance(cdp_file, Path):
        cdp = pd.read_csv(cdp_file) if cdp_file.suffix == ".csv" else pd.read_excel(cdp_file)
    else:
        name = getattr(cdp_file, "name", "").lower()
        cdp = pd.read_csv(cdp_file) if name.endswith(".csv") else pd.read_excel(cdp_file)
    cdp.columns = [c.strip() for c in cdp.columns]
    if "Company Name" in cdp.columns and "CDP Score" in cdp.columns:
        df = df.merge(cdp[["Company Name", "CDP Score"]], on="Company Name", how="left")
    return df


# ── Sustainability-report PDF parsing (on-demand) ─────────────────────────────

EMISSIONS_PATTERNS = [
    (r"scope\s*1[^a-z0-9]{0,40}([\d,\.]+)\s*(tco2e|tco2-e|t co2e|tonnes?|kt|mt)?", "Scope 1"),
    (r"scope\s*2[^a-z0-9]{0,40}([\d,\.]+)\s*(tco2e|tco2-e|t co2e|tonnes?|kt|mt)?", "Scope 2"),
    (r"scope\s*3[^a-z0-9]{0,40}([\d,\.]+)\s*(tco2e|tco2-e|t co2e|tonnes?|kt|mt)?", "Scope 3"),
]


def parse_report(pdf_bytes: bytes) -> dict:
    """Extract reported Scope 1/2/3 emissions mentions from a sustainability-report PDF."""
    try:
        import pdfplumber
    except ImportError:
        return {"error": "pdfplumber not installed. Run: pip install pdfplumber"}

    text_chunks = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:120]:
            t = page.extract_text() or ""
            text_chunks.append(t)
    text = "\n".join(text_chunks).lower()

    findings: dict[str, list[str]] = {"Scope 1": [], "Scope 2": [], "Scope 3": []}
    for pattern, label in EMISSIONS_PATTERNS:
        for m in re.finditer(pattern, text):
            value = m.group(1)
            unit = (m.group(2) or "").strip()
            findings[label].append(f"{value} {unit}".strip())

    target_mentions = re.findall(r"(net[- ]zero|carbon neutral|1\.5\s*°?c|sbti|science[- ]based target)[^.\n]{0,160}", text)

    return {
        "scope_findings": findings,
        "target_mentions": [m.strip() for m in target_mentions[:25]],
        "pages_read": len(text_chunks),
    }
