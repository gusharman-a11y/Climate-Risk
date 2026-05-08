"""Phase 1 — ASX SBTi target screen.

Pure target-side adequacy assessment (no emissions data). For each ASX-listed
SBTi company, we determine:

  1. Time-to-target (sort key — most imminent first)
  2. Scope coverage of the validated target
  3. Required scopes per SBTi sector guidance
  4. Scope-adequacy RAG (Green / Amber / Red)
  5. V2-reset likelihood (target imminent OR missing required scopes
     OR SBTi sector guidance applies but not followed)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from modules.sbti import CANON


# ─── SBTi sector guidance rulebook ─────────────────────────────────────────────
# Required scopes per SBTi published sector guidance.
# Keys are case-insensitive substrings matched against the SBTi `sector` field.
# Values: dict with required scopes, sector-pathway name, and notes.

@dataclass
class SectorRule:
    name: str                          # human-readable applicable SBTi guidance
    required: list[str]                # required scope tokens, e.g. ["S1", "S2", "S3 Cat 15"]
    note: str = ""
    applies_to: tuple[str, ...] = ()   # substrings to match in SBTi `sector` field


# Order matters — first matching rule wins. List most specific patterns first.
SECTOR_RULES: list[SectorRule] = [
    SectorRule("Financial Institutions (FINZ)",
               ["S1", "S2", "S3 Cat 15"],
               "Financed/facilitated/insured emissions (Cat 15) required.",
               applies_to=("bank", "insurance", "asset manage", "diversified financial",
                           "capital markets", "financial services", "consumer finance")),
    SectorRule("Apparel & Footwear",
               ["S1", "S2", "S3 Cat 1", "S3 Cat 11"],
               "Purchased goods (Cat 1) and use of sold products (Cat 11) required.",
               applies_to=("apparel", "footwear", "textile", "luxury goods")),
    SectorRule("Power Generation (1.5°C SDA)",
               ["S1", "S2"],
               "1.5°C-aligned Sectoral Decarbonisation Approach (SDA) required.",
               applies_to=("electric utilities", "power generation", "independent power",
                           "renewable electricity")),
    SectorRule("Cement (SDA)",
               ["S1", "S2"],
               "1.5°C-aligned cement SDA pathway required.",
               applies_to=("cement",)),
    SectorRule("Steel (SDA)",
               ["S1", "S2"],
               "1.5°C-aligned steel SDA pathway required.",
               applies_to=("steel",)),
    SectorRule("Aluminium",
               ["S1", "S2"],
               "1.5°C-aligned aluminium pathway required.",
               applies_to=("aluminium", "aluminum")),
    SectorRule("Aviation",
               ["S1", "S2", "S3 Cat 11"],
               "Use of sold products / fuel-in-use (Cat 11) required.",
               applies_to=("aviation", "airline")),
    SectorRule("Maritime",
               ["S1", "S2"],
               "1.5°C-aligned maritime pathway required.",
               applies_to=("marine", "maritime", "shipping")),
    SectorRule("ICT",
               ["S1", "S2", "S3 Cat 1", "S3 Cat 11"],
               "Devices use phase (Cat 11) and supply chain (Cat 1) required.",
               applies_to=("software", "internet", "telecom", "telecommunication",
                           "it services", "technology hardware", "data centre", "data center",
                           "communications equipment")),
    SectorRule("Buildings",
               ["S1", "S2", "S3 Cat 1", "S3 Cat 13"],
               "Embodied emissions (Cat 1) and downstream leased assets (Cat 13) required.",
               applies_to=("real estate", "reits", "construction", "homebuild",
                           "real estate management")),
    SectorRule("FLAG",
               ["S1", "S2", "S3 Cat 1"],
               "FLAG-specific targets required if ≥20% revenue from forest/land/agriculture.",
               applies_to=("food", "beverage", "tobacco", "agricultural", "forest", "paper",
                           "containers & packaging", "household products")),
    SectorRule("Land Transport",
               ["S1", "S2", "S3 Cat 11"],
               "Vehicle/fleet use phase (Cat 11) required for OEMs.",
               applies_to=("automobile", "auto parts", "auto component", "trucking", "rail",
                           "road & rail", "logistics", "transportation infrastructure")),
    SectorRule("Oil & Gas (SBTi guidance suspended)",
               ["S1", "S2", "S3 Cat 11"],
               "Use of sold products (Cat 11) is the critical category. SBTi paused new "
               "validations in March 2024; targets without Cat 11 are inadequate.",
               applies_to=("oil & gas", "oil gas", "petroleum", "integrated oil",
                           "exploration & production")),
    SectorRule("Mining & Metals",
               ["S1", "S2", "S3 Cat 11"],
               "Cat 11 critical where mined products are fossil fuels. No formal SBTi pathway "
               "yet — general corporate criteria apply.",
               applies_to=("mining", "diversified metals", "coal", "precious metals")),
    SectorRule("Chemicals",
               ["S1", "S2", "S3 Cat 11"],
               "SBTi chemicals pathway under development. Cat 11 critical for product use.",
               applies_to=("chemicals",)),
    SectorRule("Retail / Consumer (general)",
               ["S1", "S2", "S3 Cat 1"],
               "Purchased goods (Cat 1) typically dominant. General SBTi 67% Scope 3 rule applies.",
               applies_to=("retail", "consumer durable", "household appliance",
                           "leisure equipment", "personal product")),
]


def applicable_rule(sector: str | None) -> SectorRule | None:
    if not sector or pd.isna(sector):
        return None
    s = str(sector).lower()
    for rule in SECTOR_RULES:
        if any(pat in s for pat in rule.applies_to):
            return rule
    return None


# ─── Target-language scope parser ─────────────────────────────────────────────

# Match Scope 3 categories and a few common synonyms used in SBTi target wording.
S3_CATEGORY_PATTERNS: list[tuple[str, str]] = [
    (r"\bcategory\s*1\b|\bpurchased goods (?:and|&) services\b", "S3 Cat 1"),
    (r"\bcategory\s*2\b|\bcapital goods\b", "S3 Cat 2"),
    (r"\bcategory\s*3\b|\bfuel[- ]and[- ]energy[- ]related\b", "S3 Cat 3"),
    (r"\bcategory\s*4\b|\bupstream transportation\b", "S3 Cat 4"),
    (r"\bcategory\s*5\b|\bwaste generated in operations\b", "S3 Cat 5"),
    (r"\bcategory\s*6\b|\bbusiness travel\b", "S3 Cat 6"),
    (r"\bcategory\s*7\b|\bemployee commuting\b", "S3 Cat 7"),
    (r"\bcategory\s*8\b|\bupstream leased assets\b", "S3 Cat 8"),
    (r"\bcategory\s*9\b|\bdownstream transportation\b", "S3 Cat 9"),
    (r"\bcategory\s*10\b|\bprocessing of sold products\b", "S3 Cat 10"),
    (r"\bcategory\s*11\b|\buse of sold products?\b|\bproduct use phase\b", "S3 Cat 11"),
    (r"\bcategory\s*12\b|\bend[- ]of[- ]life\b", "S3 Cat 12"),
    (r"\bcategory\s*13\b|\bdownstream leased assets\b", "S3 Cat 13"),
    (r"\bcategory\s*14\b|\bfranchises?\b", "S3 Cat 14"),
    (r"\bcategory\s*15\b|\binvestments?\b|\bfinanced emissions?\b|"
     r"\bfacilitated emissions?\b|\binsured emissions?\b", "S3 Cat 15"),
]


def parse_scopes(target_text: str | None) -> set[str]:
    """Extract scope tokens (S1, S2, S3, S3 Cat N) from SBTi target wording."""
    if not target_text or pd.isna(target_text):
        return set()
    t = str(target_text).lower()
    scopes: set[str] = set()

    if re.search(r"\bscope\s*1\b|\bscopes?\s*1\s*(?:and|,|\+|&)\s*2\b", t):
        scopes.add("S1")
    if re.search(r"\bscope\s*2\b|\bscopes?\s*1\s*(?:and|,|\+|&)\s*2\b", t):
        scopes.add("S2")
    if re.search(r"\bscope\s*3\b", t):
        scopes.add("S3")
        for pattern, label in S3_CATEGORY_PATTERNS:
            if re.search(pattern, t):
                scopes.add(label)
        # If Scope 3 is mentioned but no specific category detected, leave bare "S3"
        # so reviewer can see it's covered but unspecified.
    return scopes


def format_scopes(scopes: set[str]) -> str:
    if not scopes:
        return "—"
    order = ["S1", "S2", "S3"] + [f"S3 Cat {i}" for i in range(1, 16)]
    return ", ".join([s for s in order if s in scopes])


# ─── Adequacy & V2 reset assessment ──────────────────────────────────────────

def assess_row(row: pd.Series) -> dict:
    """Phase 1 assessment. SBTi-validated targets are presumed scope-adequate
    at validation time, so we don't surface a Scope Adequacy RAG. Scope analysis
    feeds only the V2 reset flag."""
    sector = row.get(CANON["sector"])
    rule = applicable_rule(sector)
    target_text = row.get(CANON["target"])

    covered = parse_scopes(target_text)
    required = set(rule.required) if rule else set()
    missing = sorted(required - covered)

    target_year, year_source = best_target_year(row)
    this_year = datetime.utcnow().year
    yrs_to = (target_year - this_year) if target_year else None

    # ── V2 reset triggers ──
    # (a) target year ≤ 2030 (the SBTi V2 near-term horizon)
    # (b) target year already passed
    # (c) required scopes missing per applicable SBTi sector guidance
    reset_reasons: list[str] = []
    if target_year is not None:
        if target_year < this_year:
            reset_reasons.append(
                f"Target year passed ({target_year}, {abs(yrs_to)} yr"
                f"{'s' if abs(yrs_to) != 1 else ''} ago)"
            )
        elif target_year <= 2030:
            reset_reasons.append(
                f"Target due {target_year} (≤2030 V2 horizon, {yrs_to} yr"
                f"{'s' if yrs_to != 1 else ''} away)"
            )
    # Only consider scope-gap as a V2 reset trigger if a target is actually
    # validated/set. For "Committed" companies there's no target to evaluate.
    near_term_status = str(row.get(CANON["near_term_status"], "")).strip().lower()
    target_is_set = "targets set" in near_term_status or "validated" in near_term_status
    if rule and missing and target_is_set:
        reset_reasons.append(
            f"SBTi {rule.name} pathway applies but target doesn't cover "
            f"required scope{'s' if len(missing) != 1 else ''}: {', '.join(missing)}"
        )

    return {
        "Applicable SBTi Guidance": rule.name if rule else "—",
        "Target Scopes Covered": format_scopes(covered),
        "Years to Target": yrs_to if yrs_to is not None else pd.NA,
        "Target Year (used)": target_year if target_year is not None else pd.NA,
        "Year Source": year_source or "—",
        "V2 Reset Likely": "Yes" if reset_reasons else "No",
        "V2 Reset Reasons": "; ".join(reset_reasons) if reset_reasons else "—",
    }


def _to_int(v) -> int | None:
    """Coerce to a 4-digit year. Handles ints, floats, '2030', '2030.0',
    '2030-12-31', and pandas/numpy NaN."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    # Pull a 4-digit year out of any string representation.
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    m = re.search(r"(19|20)\d{2}", s)
    if m:
        return int(m.group(0))
    try:
        i = int(float(s))
        return i if 1900 < i < 2200 else None
    except Exception:
        return None


def best_target_year(row: pd.Series) -> tuple[int | None, str]:
    """Return (year, source). Falls back near-term -> long-term -> net-zero."""
    nt = _to_int(row.get(CANON["target_year"]))
    if nt is not None:
        return nt, "near-term"
    lt = _to_int(row.get(CANON["long_term_target_year"]))
    if lt is not None:
        return lt, "long-term"
    nz = _to_int(row.get(CANON["net_zero_year"]))
    if nz is not None:
        return nz, "net-zero"
    return None, ""


# ─── ASX cohort filter & screen builder ───────────────────────────────────────

# ASX-listed Australian companies whose SBTi records carry no AU ISIN
# (data-quality miss in the SBTi dataset). Hand-curated.
ASX_ALLOWLIST = {
    "Xero",                          # NZ ISIN, but ASX:XRO dual-listed
    "MoneyMe Limited",               # ASX:MME
    "Pro-Pac Packaging Limited",     # ASX:PPG
    "Pro-Pac Packaging",
}


def filter_asx(df: pd.DataFrame) -> pd.DataFrame:
    """ASX-listed cohort: Australian SBTi entries with an AU ISIN, plus a
    hand-curated allow-list of dual-listed/missing-ISIN ASX entities."""
    if df.empty:
        return df
    country = df[CANON["country"]].astype(str).str.strip().str.lower()
    isin = df[CANON["isin"]].astype(str).str.strip().str.upper()
    company = df[CANON["company"]].astype(str).str.strip()
    mask_isin = country.eq("australia") & isin.str.startswith("AU")
    mask_allow = country.eq("australia") & company.isin(ASX_ALLOWLIST)
    return df[mask_isin | mask_allow].copy()


def filter_au_private(df: pd.DataFrame) -> pd.DataFrame:
    """Other Australian large-corporate / financial-institution SBTi entries —
    everything that's Australian and Corporate/FI but not in the ASX cohort.
    Excludes SMEs."""
    if df.empty:
        return df
    country = df[CANON["country"]].astype(str).str.strip().str.lower()
    isin = df[CANON["isin"]].astype(str).str.strip().str.upper()
    company = df[CANON["company"]].astype(str).str.strip()
    org = df[CANON["org_type"]].astype(str).str.strip().str.lower()
    in_asx = country.eq("australia") & (isin.str.startswith("AU") | company.isin(ASX_ALLOWLIST))
    is_au = country.eq("australia")
    is_large = org.isin({"corporate", "financial institution"})
    return df[is_au & ~in_asx & is_large].copy()


COHORTS = {
    "ASX listed (SBTi)": filter_asx,
    "Australian Corporate / FI (SBTi, private)": filter_au_private,
    "ASX 200 — no SBTi target": None,  # Loaded from a separate CSV, not filtered from SBTi data
    "NGER reporters (not in cohort)": None,  # Loaded from NGER xlsx; large-emitter universe
}


def build_all(df: pd.DataFrame) -> pd.DataFrame:
    """Combined view of all three cohorts in one DataFrame, with a 'Cohort'
    column indicating which group each company belongs to. Used when the
    UI wants a single unified view filtered by cohort rather than a hard
    cohort switch."""
    parts = []
    for name in COHORTS:
        sub = build_screen(df, cohort=name)
        if not sub.empty:
            sub = sub.copy()
            sub["Cohort"] = name
            parts.append(sub)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True, sort=False)
    # Sort: SBTi-validated first (low Years to Target), non-SBTi by BD priority
    out = out.sort_values(
        ["Cohort", "Years to Target"],
        ascending=[True, True],
        na_position="last",
    ).reset_index(drop=True)
    return out


def build_screen(df: pd.DataFrame, cohort: str = "ASX listed (SBTi)") -> pd.DataFrame:
    """Phase 1 output: cohort + adequacy + V2 reset columns,
    sorted by Years to Target ascending (NaN last).

    For the 'ASX 200 — no SBTi target' cohort, df is ignored and data is
    loaded from data/asx200_non_sbti.csv via modules.asx200.
    """
    if cohort == "ASX 200 — no SBTi target":
        from modules.asx200 import load_asx200, to_phase1_shape
        sub = to_phase1_shape(load_asx200())
        if sub.empty:
            return sub
        extra = sub.apply(assess_row, axis=1, result_type="expand")
        out = pd.concat([sub.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)
        if "BD Priority" in out.columns:
            out = out.sort_values("BD Priority", ascending=False).reset_index(drop=True)
        return out

    if cohort == "NGER reporters (not in cohort)":
        from modules.nger import build_nger_only_cohort
        # Compute the names already represented in the SBTi + ASX200 cohorts so
        # we can de-dup against them.
        already = []
        for other in ("ASX listed (SBTi)", "Australian Corporate / FI (SBTi, private)",
                      "ASX 200 — no SBTi target"):
            try:
                other_sub = build_screen(df, cohort=other)
                if not other_sub.empty:
                    already.extend(other_sub["Company Name"].astype(str).tolist())
            except Exception:
                continue
        sub = build_nger_only_cohort(already)
        if sub.empty:
            return sub
        extra = sub.apply(assess_row, axis=1, result_type="expand")
        out = pd.concat([sub.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)
        return out

    if df.empty:
        return df
    fn = COHORTS.get(cohort)
    if fn is None:
        return df.iloc[:0]
    sub = fn(df)
    if sub.empty:
        return sub
    # Compute ASRS Tier for SBTi cohorts (proxy via Org Type since we don't have
    # revenue/assets/employees numbers).
    if "ASRS Tier" not in sub.columns:
        from modules.sbti import asrs_tier
        sub = sub.copy()
        sub["ASRS Tier"] = sub.apply(asrs_tier, axis=1)
    extra = sub.apply(assess_row, axis=1, result_type="expand")
    out = pd.concat([sub.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)
    out = out.sort_values("Years to Target", ascending=True, na_position="last").reset_index(drop=True)
    return out


# ─── Display column order ────────────────────────────────────────────────────
# Scope adequacy is omitted intentionally — SBTi has signed these targets off,
# so we presume scope coverage was deemed adequate at validation time. The
# scope analysis still runs internally and feeds the V2 Reset flag.

# Note: ISIN intentionally omitted from default display — not useful for BD work.
DISPLAY_COLS = [
    CANON["company"], "Cohort", "ASRS Tier", CANON["sector"],
    "Applicable SBTi Guidance",
    "MQ Level", "CP Alignment",
    CANON["near_term_status"], "Target Year (used)", "Year Source", "Years to Target",
    "Target Scopes Covered",
    "V2 Reset Likely", "V2 Reset Reasons",
    "Latest Reported Year", "Required Reduction % (now)", "Actual Reduction % (now)",
    "Gap to Path (pp)", "Delivery RAG", "Data Source",
    CANON["net_zero_year"], CANON["long_term_status"], CANON["net_zero_status"],
    CANON["target_class_long"], CANON["removal_reason"],
    CANON["date_updated"],
]


V2_COLOUR = {
    "Yes": "#DC2626",
    "No": "#16A34A",
}
