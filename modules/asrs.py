"""ASRS mandatory reporting groups and BD prioritisation.

Australian Sustainability Reporting Standards (AASB S2) — mandatory phased
reporting under the Corporations Amendment (Sustainability Reporting) Act 2024.

Three groups, each with different size thresholds and mandatory start dates:
  Group 1  — periods beginning on or after 1 January 2025
  Group 2  — periods beginning on or after 1 July 2026
  Group 3  — periods beginning on or after 1 July 2027

Size tests use Corporations Act "large entity" criteria: ≥2 of 3 thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# ── Group thresholds (Corporations Amendment Act 2024) ─────────────────────────

@dataclass(frozen=True)
class AsrsGroup:
    label: str                  # "Group 1" / "Group 2" / "Group 3"
    mandatory_from: str         # ISO date string, period START date
    revenue_aud: float          # consolidated revenue threshold
    assets_aud: float           # consolidated gross assets threshold
    employees: int              # headcount threshold
    # ≥2 of the 3 thresholds above must be met


GROUP_1 = AsrsGroup(
    label="Group 1",
    mandatory_from="2025-01-01",
    revenue_aud=500_000_000,
    assets_aud=1_000_000_000,
    employees=500,
)

GROUP_2 = AsrsGroup(
    label="Group 2",
    mandatory_from="2026-07-01",
    revenue_aud=200_000_000,
    assets_aud=500_000_000,
    employees=250,   # s292A Corporations Act: 250 employees (not 500)
)

GROUP_3 = AsrsGroup(
    label="Group 3",
    mandatory_from="2027-07-01",
    revenue_aud=50_000_000,
    assets_aud=25_000_000,
    employees=100,
)

ALL_GROUPS = [GROUP_1, GROUP_2, GROUP_3]

# ── Mandatory reporting period labels (assumes June 30 FY unless otherwise noted)

GROUP_FIRST_REPORT = {
    "Group 1": "FY2025/26 — reports due ~Nov 2026",
    "Group 2": "FY2026/27 — reports due ~Nov 2027",
    "Group 3": "FY2027/28 — reports due ~Nov 2028",
}

GROUP_URGENCY_NOTE = {
    "Group 1": (
        "⚠️ Mandatory NOW. First ASRS report covers FY2025/26 (year ending 30 Jun 2026). "
        "Companies without a credible climate strategy face disclosure of gaps in 2026."
    ),
    "Group 2": (
        "🕐 Mandatory from FY2026/27. Boards need strategy in place by mid-2026 — "
        "one financial year away. Engagement window: now through end-2025."
    ),
    "Group 3": (
        "📅 Mandatory from FY2027/28. Early movers will use 2025-26 to get ahead of "
        "disclosure requirements. Still the right time to start."
    ),
}

# ── Market Cap Tier → ASRS Group proxy (when financial data unavailable) ────────
# ASX convention: Mega > $10B, Large $2B-$10B, Mid $300M-$2B, Small $50M-$300M

MARKET_CAP_TO_GROUP: dict[str, str] = {
    "mega":  "Group 1",
    "large": "Group 1",
    "mid":   "Group 2",
    "small": "Group 3",
    "micro": "Group 3",
}

# ── BD priority scoring ────────────────────────────────────────────────────────
# Higher score = stronger BD signal.

TARGET_CLASS_URGENCY = {
    "No public target":              5,
    "Aspirational":                  4,
    "Net-zero only":                 3,
    "Quantitative non-validated":    2,
    "SBTi committed":                1,
    "Targets set":                   0,   # Validated — low BD urgency
}

GROUP_MULTIPLIER = {
    "Group 1": 3,
    "Group 2": 2,
    "Group 3": 1,
    "Unclassified": 1,
}


def bd_priority_score(target_classification: str, asrs_group: str) -> int:
    """Combined BD priority score (0–15). Higher = more urgent outreach.
    Derived from ASRS reporting urgency × climate target gap."""
    t = TARGET_CLASS_URGENCY.get(str(target_classification).strip(), 2)
    g = GROUP_MULTIPLIER.get(str(asrs_group).strip(), 1)
    return t * g


def bd_priority_label(score: int) -> str:
    if score >= 12:
        return "🔴 Critical"
    if score >= 8:
        return "🟠 High"
    if score >= 4:
        return "🟡 Medium"
    return "🟢 Low"


_GROUP_DEADLINE = {
    "Group 1": "mandatory now (FY2025/26)",
    "Group 2": "mandatory FY2026/27",
    "Group 3": "mandatory FY2027/28",
    "Unclassified": "ASRS group unconfirmed",
}

_TARGET_GAP_NOTE = {
    "No public target": "no public climate target — ASRS disclosure without any strategy",
    "Aspirational": "aspirational target only — no near-term quantitative pathway",
    "Net-zero only": "net-zero commitment but no near-term science-based target",
    "Quantitative non-validated": "quantitative target set but not independently validated",
    "SBTi committed": "SBTi intent letter submitted — target validation in progress",
    "Targets set": "SBTi validated — monitor for V2 reset or delivery gap",
}


def bd_rationale(target_classification: str, asrs_group: str) -> str:
    """One-line plain-English BD rationale for reviewers."""
    tc = str(target_classification).strip()
    grp = str(asrs_group).strip()
    deadline = _GROUP_DEADLINE.get(grp, "ASRS group unconfirmed")
    gap = _TARGET_GAP_NOTE.get(tc, "target status unclear")
    return f"{grp} — {deadline}; {gap}"


# ── Group classifier ───────────────────────────────────────────────────────────

def _meets_group(row: pd.Series, g: AsrsGroup) -> bool:
    hits = 0
    if float(row.get("Revenue (AUD)", 0) or 0) >= g.revenue_aud:
        hits += 1
    if float(row.get("Assets (AUD)", 0) or 0) >= g.assets_aud:
        hits += 1
    if float(row.get("Employees", 0) or 0) >= g.employees:
        hits += 1
    return hits >= 2


def asrs_group(row: pd.Series) -> str:
    """Return ASRS Group label for a cohort row.

    Uses verified financial data (Revenue/Assets/Employees) when available;
    falls back to Market Cap Tier proxy for ASX 200 companies where financial
    data is not populated.

    Returns: 'Group 1', 'Group 2', 'Group 3', or 'Unclassified'.
    """
    # Try verified financial data first
    has_financial = any(float(row.get(c, 0) or 0) > 0
                        for c in ("Revenue (AUD)", "Assets (AUD)", "Employees"))
    if has_financial:
        for g in ALL_GROUPS:
            if _meets_group(row, g):
                return g.label
        return "Group 3"   # Has financial data but below Group 2 → small entity

    # Proxy: Market Cap Tier
    mc = str(row.get("Market Cap Tier", "")).strip().lower()
    if mc in MARKET_CAP_TO_GROUP:
        return MARKET_CAP_TO_GROUP[mc]

    # Proxy: ASRS Tier column (backward compat with old sbti.py values)
    tier = str(row.get("ASRS Tier", "")).strip()
    if tier == "Tier 1":
        return "Group 1"
    if tier == "Tier 2":
        return "Group 2"
    if tier == "Tier 3":
        return "Group 3"

    return "Unclassified"


def first_mandatory_report(group: str) -> str:
    return GROUP_FIRST_REPORT.get(group, "—")


def add_asrs_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich a cohort dataframe with ASRS Group, first report period,
    BD priority score, and BD priority label columns."""
    df = df.copy()
    df["ASRS Group"] = df.apply(asrs_group, axis=1)
    df["First Mandatory Report"] = df["ASRS Group"].map(GROUP_FIRST_REPORT).fillna("—")
    target_col = next(
        (c for c in ("Target Classification", "Target Classification (BD)")
         if c in df.columns), None
    )
    if target_col:
        df["BD Priority Score"] = df.apply(
            lambda r: bd_priority_score(r.get(target_col, ""), r.get("ASRS Group", "")),
            axis=1,
        )
        df["BD Priority"] = df["BD Priority Score"].apply(bd_priority_label)
        df["BD Rationale"] = df.apply(
            lambda r: bd_rationale(r.get(target_col, ""), r.get("ASRS Group", "")),
            axis=1,
        )
    return df
