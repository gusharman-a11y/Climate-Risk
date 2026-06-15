"""ATO Corporate Tax Transparency — large private entity cohort.

Source: data.gov.au — "Corporate Transparency" dataset (ATO)
Download: https://data.gov.au/data/dataset/corporate-transparency

Commit the latest annual Excel to data/ato_transparency.xlsx (or
data/ato_transparency_YYYY-YY.xlsx). The loader finds it automatically.

Sheet used: "Income tax details"
Columns:    Name | ABN | Total income $ | Taxable income $ | Tax payable $ | Income year

Private-company detection:
  1. Name contains "PTY" → private (catches PTY LTD, PTY LIMITED)
  2. Cross-reference against ASXListedCompanies.csv → exclude listed entities

ASRS Group proxy (income only — no assets/employee data available):
  Total income ≥ $500M → Group 1 proxy  (revenue threshold ≥ $500M likely met)
  Total income ≥ $200M → Group 2 proxy  (revenue threshold ≥ $200M likely met)
  Total income  < $200M → not included  (below Group 2 revenue floor)

Public API:
  find_committed_ato()            — locate data/ato_transparency*.xlsx
  load_ato(file)                  — load, filter, return clean DataFrame
  build_ato_cohort(existing)      — return phase1-shape DataFrame, deduped
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Minimum total income to include (AUD). Group 2 revenue floor = $200M.
INCOME_MIN_AUD: int = 200_000_000

_STRIP_TOKENS = re.compile(
    r"\b(?:pty|ltd|limited|corporation|corp|incorporated|inc|"
    r"group|holdings|holding|company|co\b|plc|the|and|"
    r"australia|australian)\b",
    re.I,
)


def _name_key(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    n = _STRIP_TOKENS.sub("", n)
    return re.sub(r"\s+", " ", n).strip()


def _name_match(key_a: str, key_b: str) -> bool:
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    ta, tb = key_a.split(), key_b.split()
    if not ta or not tb:
        return False
    if ta[0] == tb[0]:
        overlap = len(set(ta) & set(tb))
        if overlap >= min(2, len(ta)):
            return True
    if len(key_a) >= 6 and key_b.startswith(key_a[:6]):
        return True
    if len(key_b) >= 6 and key_a.startswith(key_b[:6]):
        return True
    return False


# ── File discovery ────────────────────────────────────────────────────────────

def find_committed_ato() -> Path | None:
    """Return the most recent ato_transparency*.xlsx in data/, or None."""
    if not DATA_DIR.exists():
        return None
    candidates = [
        p for p in DATA_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".xlsx"
        and "ato" in p.name.lower()
    ]
    if not candidates:
        return None
    def _year(p: Path) -> int:
        m = re.search(r"(20\d{2})", p.name)
        return int(m.group(1)) if m else 0
    candidates.sort(key=lambda p: (_year(p), p.stat().st_mtime), reverse=True)
    return candidates[0]


# ── Loader ────────────────────────────────────────────────────────────────────

def load_ato(file=None) -> pd.DataFrame:
    """Load ATO Corporate Tax Transparency Excel.

    Accepts a Path, bytes, or file-like object.  Falls back to
    find_committed_ato() if file is None.  Returns a clean DataFrame with
    columns: Name, ABN, Total Income (AUD), Income Year.
    Only rows with Total Income ≥ INCOME_MIN_AUD are kept.
    """
    if file is None:
        file = find_committed_ato()
    if file is None:
        return pd.DataFrame()

    try:
        df = pd.read_excel(file, sheet_name="Income tax details")
    except Exception:
        try:
            df = pd.read_excel(file, sheet_name=0)
        except Exception:
            return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]

    # Normalise column names
    rename = {}
    for c in df.columns:
        lc = c.lower()
        if "name" in lc and "entity" not in lc:
            rename[c] = "Name"
        elif lc == "abn":
            rename[c] = "ABN"
        elif "total income" in lc:
            rename[c] = "Total Income (AUD)"
        elif "income year" in lc:
            rename[c] = "Income Year"
    df = df.rename(columns=rename)

    required = {"Name", "Total Income (AUD)"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df = df[df["Name"].notna()].copy()
    df["Total Income (AUD)"] = pd.to_numeric(df["Total Income (AUD)"], errors="coerce")
    df = df[df["Total Income (AUD)"] >= INCOME_MIN_AUD].copy()
    df["Name"] = df["Name"].astype(str).str.strip().str.title()
    if "ABN" in df.columns:
        df["ABN"] = df["ABN"].astype(str).str.strip().str.replace(r"\D", "", regex=True)
    return df.reset_index(drop=True)


# ── Is-listed check ───────────────────────────────────────────────────────────

def _build_asx_name_keys() -> set[str]:
    """Return the set of normalised name keys for ASX-listed companies."""
    try:
        from modules.asx_listings import load_asx_listings
        listings = load_asx_listings()
        if listings.empty or "_key" not in listings.columns:
            return set()
        return set(listings["_key"].dropna())
    except Exception:
        return set()


def _is_private(name: str, asx_keys: set[str]) -> bool:
    """Return True if the entity is likely unlisted/private."""
    # Fast path: contains "Pty" → private
    if re.search(r"\bpty\b", name, re.I):
        return True
    # Cross-reference against ASX listings
    k = _name_key(name)
    if not k:
        return True
    if k in asx_keys:
        return False
    # Fuzzy fallback: if any ASX key is a close match, treat as listed
    for ak in asx_keys:
        if _name_match(k, ak):
            return False
    return True


# ── Cohort builder ────────────────────────────────────────────────────────────

def _asrs_tier_from_income(income: float) -> str:
    if income >= 500_000_000:
        return "Tier 1"
    return "Tier 2"


def build_ato_cohort(existing_cohort_names: list[str]) -> pd.DataFrame:
    """Return a phase1-shape DataFrame of large private Australian entities
    not already represented in another cohort.

    Parameters
    ----------
    existing_cohort_names : list of Company Name strings already in the tool
        (SBTi ASX + SBTi private + ASX 200 + NGER-only cohorts).
    """
    ato = load_ato()
    if ato.empty:
        return pd.DataFrame()

    asx_keys = _build_asx_name_keys()

    # 1. Keep only private / unlisted entities
    ato = ato[ato["Name"].apply(lambda n: _is_private(n, asx_keys))].copy()
    if ato.empty:
        return pd.DataFrame()

    # 2. Deduplicate against other cohorts
    existing_keys = {_name_key(n) for n in existing_cohort_names if n}
    ato["_key"] = ato["Name"].apply(_name_key)
    already = set()
    for idx, row in ato.iterrows():
        k = row["_key"]
        if not k:
            already.add(idx)
            continue
        if k in existing_keys:
            already.add(idx)
            continue
        # Fuzzy match against existing
        for ek in existing_keys:
            if _name_match(k, ek):
                already.add(idx)
                break
    ato = ato[~ato.index.isin(already)].reset_index(drop=True)
    if ato.empty:
        return pd.DataFrame()

    # 3. Build phase1-shape output
    out = pd.DataFrame()
    out["Company Name"]               = ato["Name"]
    out["ISIN"]                       = ""
    out["Country"]                    = "Australia"
    out["Region"]                     = "Oceania"
    out["Sector"]                     = "Not classified"
    out["Industry"]                   = ""
    out["Organization Type"]          = "Private"
    out["Near-term Status"]           = ""
    out["Long-term Status"]           = ""
    out["Net-Zero Status"]            = ""
    out["Target"]                     = ""
    out["Target Year"]                = pd.NA
    out["Long-term Target Year"]      = pd.NA
    out["Net-Zero Year"]              = pd.NA
    out["Target Classification"]      = "No public target"
    out["Target Classification (Long)"] = "No public target"
    out["BA1.5 Status"]               = ""
    out["BA1.5 Date"]                 = ""
    out["Removal/Extension Reason"]   = ""
    out["Date Committed"]             = pd.NA
    out["Date Published"]             = pd.NA
    out["Date Updated"]               = pd.NA
    out["SBTi ID"]                    = ""
    out["LEI"]                        = ""
    out["Base Year"]                  = pd.NA
    out["Ambition"]                   = ""

    if "ABN" in ato.columns:
        out["ABN"] = ato["ABN"].values
    out["ATO Total Income (AUD)"] = ato["Total Income (AUD)"].values
    out["ASRS Tier"] = ato["Total Income (AUD)"].apply(_asrs_tier_from_income)

    # Sort by income descending — largest emitters / highest-ASRS-urgency first
    out = out.sort_values("ATO Total Income (AUD)", ascending=False).reset_index(drop=True)

    return out
