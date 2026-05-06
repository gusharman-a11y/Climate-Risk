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
    "company": "Company Name",
    "isin": "ISIN",
    "lei": "LEI",
    "country": "Country",
    "region": "Region",
    "sector": "Sector",
    "industry": "Industry",
    "org_type": "Organization Type",
    "action": "Action",
    "target": "Target",
    "target_class": "Target Classification",
    "target_year": "Target Year",
    "base_year": "Base Year",
    "status": "Status",
    "near_term_status": "Near-term Status",
    "net_zero_year": "Net-Zero Year",
    "ambition": "Ambition",
    "date_committed": "Date Committed",
    "date_published": "Date Published",
}

# Common header variants seen in SBTi exports → canonical name.
ALIASES = {
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
    "primary sub-sector": "industry",
    "organization type": "org_type",
    "company classification": "org_type",
    "action": "action",
    "target wording": "target",
    "target": "target",
    "target classification": "target_class",
    "target classification (short)": "target_class",
    "near term - target classification": "target_class",
    "target year": "target_year",
    "near-term - target year": "target_year",
    "base year": "base_year",
    "near-term - base year": "base_year",
    "status": "status",
    "near-term - target status": "near_term_status",
    "near term - target status": "near_term_status",
    "net-zero year": "net_zero_year",
    "long term - target year": "net_zero_year",
    "ambition": "ambition",
    "near-term - ambition": "ambition",
    "date - committed": "date_committed",
    "date committed": "date_committed",
    "date - published": "date_published",
    "date published": "date_published",
    "target submitted to sbti": "date_committed",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = re.sub(r"\s+", " ", str(col)).strip().lower()
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
# Group 1: ≥2 of (revenue ≥ A$500M, assets ≥ A$1B, employees ≥ 500)
# Group 2: ≥2 of (revenue ≥ A$200M, assets ≥ A$500M, employees ≥ 250)


@dataclass
class AsrsThresholds:
    revenue_aud: float
    assets_aud: float
    employees: int


GROUP_1 = AsrsThresholds(500_000_000, 1_000_000_000, 500)
GROUP_2 = AsrsThresholds(200_000_000, 500_000_000, 250)


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
    """Return 'Group 1', 'Group 2', 'Group 3', or 'Unclassified'."""
    if _meets(row, GROUP_1):
        return "Group 1"
    if _meets(row, GROUP_2):
        return "Group 2"
    if any(row.get(c, 0) for c in ("Revenue (AUD)", "Assets (AUD)", "Employees")):
        return "Group 3"
    # Fallback proxy: SBTi 'Organization Type' = 'Company' (Large) → assume Group 2 candidate.
    org = str(row.get(CANON["org_type"], "")).lower()
    if "sme" in org:
        return "Group 3"
    if "company" in org or "financial" in org:
        return "Group 2 (proxy)"
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


def _score_row(row: pd.Series) -> dict:
    status = str(row.get(CANON["status"], "")).strip().lower()
    near_term = str(row.get(CANON["near_term_status"], "")).strip().lower()
    ambition = str(row.get(CANON["ambition"], "")).strip().lower()
    target_year = _to_int(row.get(CANON["target_year"]))
    nz_year = _to_int(row.get(CANON["net_zero_year"]))

    # 1. Status (max 3, min -2)
    status_pts = 0
    for key, pts in STATUS_POINTS.items():
        if key in status or key in near_term:
            status_pts = max(status_pts, pts) if pts >= 0 else min(status_pts, pts)
    if not status_pts and ("removed" in status or "removed" in near_term):
        status_pts = -2

    # 2. Ambition (max 3)
    ambition_pts = 0
    for key, pts in AMBITION_POINTS.items():
        if key in ambition:
            ambition_pts = max(ambition_pts, pts)

    # 3. Net-zero commitment (1)
    nz_pts = 1 if nz_year else 0

    # 4. Target-year freshness — penalise expired without renewal (-2)
    this_year = datetime.utcnow().year
    expired_pts = 0
    if target_year and target_year < this_year and "set" not in status:
        expired_pts = -2

    # 5. Disclosure recency (max 2)
    rec_pts = 0
    for col in (CANON["date_published"], CANON["date_committed"]):
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
