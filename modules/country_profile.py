"""Generic country company profile builder.

Reusable functions for matching any exchange company list against the global
SBTi Companies Taking Action register, then building a BD-ready profile screen
that mirrors the Australian AUS Company Profile tab layout.

Used by the Philippines (PSE) and Malaysia (Bursa) tabs.
"""
from __future__ import annotations

import re

import pandas as pd

from modules.sbti import CANON
from modules.asrs import TARGET_CLASS_URGENCY, bd_priority_label

# ── Name normalisation (shared with safeguard.py / voluntary.py) ──────────────

_STRIP_TOKENS = re.compile(
    r"\b(?:corporation|corp|incorporated|inc|limited|ltd|berhad|bhd|"
    r"group|holdings|holding|company|co\b|plc|pte|sdn|tbk|the|and|"
    r"philippines|philippine|malaysia|malaysian|australia|australian)\b",
    re.I,
)


def _name_key(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    n = _STRIP_TOKENS.sub("", n)
    return re.sub(r"\s+", " ", n).strip()


def _name_match(key_a: str, key_b: str) -> bool:
    """Return True if two normalised name keys are similar enough to be the same company."""
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    ta = key_a.split()
    tb = key_b.split()
    if not ta or not tb:
        return False
    # Same first word + ≥2 tokens in common
    if ta[0] == tb[0]:
        overlap = len(set(ta) & set(tb))
        if overlap >= min(2, len(ta)):
            return True
    # Prefix: one starts with at least 6 chars of the other
    if len(key_a) >= 6 and key_b.startswith(key_a[:6]):
        return True
    if len(key_b) >= 6 and key_a.startswith(key_b[:6]):
        return True
    return False


# ── SBTi country filter ───────────────────────────────────────────────────────

def filter_sbti_country(
    df: pd.DataFrame,
    country_name: str,
    isin_prefix: str | None = None,
) -> pd.DataFrame:
    """Return rows from the global SBTi register matching a country.

    Matches on the Country column (case-insensitive).  Optionally also matches
    on ISIN prefix (e.g. 'PH' for Philippines, 'MY' for Malaysia) to catch
    entries where Country may be missing but ISIN is present.
    """
    if df.empty:
        return df.head(0)
    country_col = df[CANON["country"]].astype(str).str.strip().str.lower()
    mask = country_col.eq(country_name.lower())
    if isin_prefix:
        isin_col = df[CANON["isin"]].astype(str).str.strip().str.upper()
        mask = mask | isin_col.str.startswith(isin_prefix.upper())
    return df[mask].copy()


# ── Exchange ↔ SBTi matching ─────────────────────────────────────────────────

def match_exchange_to_sbti(
    exchange_df: pd.DataFrame,
    sbti_df: pd.DataFrame,
    exchange_name_col: str = "Company Name",
) -> pd.DataFrame:
    """Fuzzy-match every row in `exchange_df` to the nearest SBTi entry.

    Returns `exchange_df` enriched with SBTi columns where a match was found.
    Unmatched rows get SBTi="No" and blank target columns.
    """
    if sbti_df.empty:
        result = exchange_df.copy()
        result["SBTi"] = "No"
        for col in (CANON["near_term_status"], CANON["target"], CANON["target_class"],
                    CANON["net_zero_year"], CANON["target_year"]):
            result[col] = pd.NA
        return result

    # Build lookup: normalised key → first matching SBTi row
    sbti_lookup: dict[str, pd.Series] = {}
    for _, row in sbti_df.iterrows():
        key = _name_key(str(row.get(CANON["company"], "")))
        if key and key not in sbti_lookup:
            sbti_lookup[key] = row

    sbti_cols = [CANON["company"], CANON["isin"], CANON["near_term_status"],
                 CANON["target"], CANON["target_class"], CANON["target_class_long"],
                 CANON["net_zero_year"], CANON["net_zero_status"],
                 CANON["target_year"], CANON["ambition"],
                 CANON["date_committed"], CANON["date_updated"]]
    sbti_cols = [c for c in sbti_cols if c in sbti_df.columns]

    rows = []
    for _, exc_row in exchange_df.iterrows():
        exc_name = str(exc_row.get(exchange_name_col, ""))
        exc_key = _name_key(exc_name)

        match = None
        if exc_key in sbti_lookup:
            match = sbti_lookup[exc_key]
        else:
            for sk, sr in sbti_lookup.items():
                if _name_match(exc_key, sk):
                    match = sr
                    break

        merged = exc_row.to_dict()
        if match is not None:
            merged["SBTi"] = "Yes"
            for col in sbti_cols:
                if col != CANON["company"]:  # don't overwrite exchange name with SBTi name
                    merged[col] = match.get(col, pd.NA)
        else:
            merged["SBTi"] = "No"
            for col in sbti_cols:
                if col not in merged:
                    merged[col] = pd.NA

        rows.append(merged)

    return pd.DataFrame(rows)


# ── Target classification for non-SBTi companies ────────────────────────────

def infer_target_classification(row: pd.Series) -> str:
    """Infer a 6-tier Target Classification for a company.

    For SBTi companies, maps Near-term Status to the classification.
    For non-SBTi companies, returns 'No public target' as the safe default
    (a research overlay can improve this later).
    """
    sbti = str(row.get("SBTi", "No")).strip()
    near_term = str(row.get(CANON["near_term_status"], "")).strip().lower()

    if sbti == "Yes":
        if "targets set" in near_term or "validated" in near_term:
            return "Targets set"
        if "committed" in near_term and "removed" not in near_term:
            return "SBTi committed"
        if "removed" in near_term or "expired" in near_term:
            return "Quantitative non-validated"
        return "SBTi committed"

    # Non-SBTi — default, can be overridden by research overlay
    return "No public target"


# ── BD Priority ───────────────────────────────────────────────────────────────

_GROUP_DEADLINE_GENERIC = {
    "Tier 1": "mandatory now",
    "Tier 2": "mandatory soon",
    "Tier 3": "mandatory from 2027+",
    "Main Market": "mandatory now (Bursa Sustainability Reporting)",
    "ACE Market": "mandatory from 2026 (Bursa enhanced sustainability reporting)",
    "LEAP Market": "voluntary",
    "PSE Main Board": "mandatory now (Philippines SEC SRG)",
    "PSE SME Board": "emerging requirements",
    "Unclassified": "reporting framework unconfirmed",
}

_TARGET_GAP_NOTE = {
    "No public target": "no public climate target",
    "Aspirational": "aspirational target only — no near-term pathway",
    "Net-zero only": "net-zero commitment without near-term science-based target",
    "Quantitative non-validated": "quantitative target but not independently validated",
    "SBTi committed": "SBTi intent letter submitted — validation in progress",
    "Targets set": "SBTi validated — monitor for delivery gap",
}

_TIER_MULTIPLIER = {
    "Tier 1": 3, "Main Market": 3, "PSE Main Board": 3,
    "Tier 2": 2, "ACE Market": 2, "PSE SME Board": 1,
    "Tier 3": 1, "LEAP Market": 1,
    "Unclassified": 1,
}


def bd_priority_score_country(target_classification: str, tier: str) -> int:
    t = TARGET_CLASS_URGENCY.get(str(target_classification).strip(), 2)
    g = _TIER_MULTIPLIER.get(str(tier).strip(), 1)
    return t * g


def bd_rationale_country(target_classification: str, tier: str) -> str:
    tc = str(target_classification).strip()
    t = str(tier).strip()
    deadline = _GROUP_DEADLINE_GENERIC.get(t, "reporting framework unconfirmed")
    gap = _TARGET_GAP_NOTE.get(tc, "target status unclear")
    return f"{t} — {deadline}; {gap}"


# ── Full profile builder ──────────────────────────────────────────────────────

def build_country_profile(
    exchange_df: pd.DataFrame,
    sbti_df: pd.DataFrame,
    exchange_name_col: str,
    tier_fn,          # callable(row) -> str  e.g. "PSE Main Board" / "Main Market"
    tier_col_label: str,  # column header e.g. "PSE Board" / "Bursa Market"
    reporting_framework_note: str = "",
) -> pd.DataFrame:
    """Build the full BD-ready profile table for a country.

    Steps:
    1. Fuzzy-match exchange companies to SBTi entries
    2. Infer target classification
    3. Assign exchange-specific tier
    4. Calculate BD Priority and BD Rationale
    5. Return enriched DataFrame with consistent column set
    """
    if exchange_df.empty:
        return pd.DataFrame()

    # 1. SBTi overlay
    profile = match_exchange_to_sbti(exchange_df, sbti_df, exchange_name_col)

    # 2. Target classification
    profile["Target Classification"] = profile.apply(infer_target_classification, axis=1)

    # 3. Tier
    profile[tier_col_label] = profile.apply(tier_fn, axis=1)

    # 4. BD Priority
    profile["BD Priority Score"] = profile.apply(
        lambda r: bd_priority_score_country(
            r.get("Target Classification", ""),
            r.get(tier_col_label, ""),
        ),
        axis=1,
    )
    profile["BD Priority"] = profile["BD Priority Score"].apply(bd_priority_label)
    profile["BD Rationale"] = profile.apply(
        lambda r: bd_rationale_country(
            r.get("Target Classification", ""),
            r.get(tier_col_label, ""),
        ),
        axis=1,
    )

    # 5. Profile source
    profile["Profile Source"] = profile["SBTi"].apply(
        lambda s: "SBTi Companies Taking Action" if s == "Yes" else "Exchange listing only"
    )

    return profile.sort_values("BD Priority Score", ascending=False).reset_index(drop=True)
