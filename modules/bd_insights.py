"""BD Insights — pre-canned strategic analyses of the cohort.

Each insight is a function that takes the full cohort DataFrame and returns:
    {
        "title": short headline,
        "summary": 1-3 sentence framing,
        "table": pd.DataFrame of relevant companies (or None),
        "table_caption": caption for the table,
    }

To add a new insight, write a function and register it in INSIGHTS.
"""

from __future__ import annotations

import pandas as pd

from modules.sbti import CANON


# ─── Individual insights ─────────────────────────────────────────────────────

def top_bd_targets(df: pd.DataFrame) -> dict:
    """Curated top 10 — companies with both a strategic moment and a credibility
    gap. Hand-selected names from training-data BD signals research."""
    top10 = [
        ("Pioneer Sail Holdings Pty Limited", "Sembcorp $4.3bn acquisition pending Dec 2025; 2.7Mt 2030 group target acknowledged unachievable post-Alinta"),
        ("EnergyAustralia Holdings Limited", "May 2025 greenwashing case settled with Parents for Climate; ACCU/offset strategy under review; Yallourn closure 2028"),
        ("Stanwell Corporation Limited", "AU #1 NGER S1 emitter (17.9Mt); no entity SBTi; LNP government reviewing QEJP"),
        ("Woodside Energy Group Ltd", "58% shareholder rejection of CTAP at 2024 AGM; Aug 2025 Woodside-Santos merger pending; SBTi withdrawn"),
        ("Chevron Australia Holdings Pty Ltd", "Gorgon CCS underperforming (~30-40% vs design); ACCU/Safeguard exposure; foreign-parent ASRS complexity"),
        ("Fortescue Metals Group Ltd", "Real Zero S1+S2 by 2030 — most aggressive in cohort; publicly rejected SBTi 2024; $6.2bn capex committed"),
        ("BHP Group Limited", "Largest miner; SBTi committed but not validated; recently divested Blackwater/Daunia; growing S3 product-use scrutiny"),
        ("Coles Group Limited", "SBTi-validated 75% S1+S2 by FY35 — most ambitious retail target; Scope 3 supplier engagement at scale"),
        ("AGL Energy", "Coal exit 2035 accelerated from 2045; 78% S1+S2 reduction by FY34-35; 5GW+ renewables pipeline"),
        ("Origin Energy", "60% S1+S2+S3 by 2035 from FY17 (ratchet-up); Eraring closure delayed to 2027; SBTi pre-validation"),
    ]
    rows = []
    for name, why in top10:
        match = df[df["Company Name"] == name]
        if match.empty:
            # Try substring match
            match = df[df["Company Name"].str.contains(name.split()[0], na=False, case=False)]
        if not match.empty:
            r = match.iloc[0]
            rows.append({
                "Company Name": r["Company Name"],
                "ASX Code": r.get("ASX Code", "") or "—",
                "Cohort": r.get("Cohort", ""),
                "SBTi Status": r.get(CANON["near_term_status"], "") or "—",
                "Why now": why,
            })
    return {
        "title": "Top 10 BD targets — strategic moment + credibility gap",
        "summary": (
            "Curated list: every entry has either a strategic decision point in "
            "the next 12 months (merger / target revision / regulatory deadline) "
            "or a credibility gap to close (greenwashing case / shareholder revolt "
            "/ SBTi withdrawal / CCS underperformance). That's where advisory "
            "fees concentrate."
        ),
        "table": pd.DataFrame(rows),
        "table_caption": "Sorted by BD priority. Verify via Source URL before outreach.",
    }


def sbti_commitment_removed(df: pd.DataFrame) -> dict:
    """SBTi commitment removed — re-engagement opportunities."""
    rem = df[df[CANON["near_term_status"]].astype(str).str.lower().str.contains(
        "removed", na=False)].copy()
    cols = ["Company Name", "ASX Code", "Cohort", "Target Year (used)",
            CANON["net_zero_year"], CANON["removal_reason"]]
    cols = [c for c in cols if c in rem.columns]
    rem = rem[cols].sort_values("Company Name")
    return {
        "title": f"SBTi commitments removed ({len(rem)} companies)",
        "summary": (
            "These companies submitted an SBTi intent letter then withdrew "
            "(usually because they couldn't meet the 24-month validation deadline "
            "or refused to commit to Scope 3). Re-engagement opportunity: help "
            "them rebuild a credible target before V2 / ASRS pressure intensifies."
        ),
        "table": rem,
        "table_caption": "Sorted A–Z by company.",
    }


def behind_on_delivery(df: pd.DataFrame) -> dict:
    """Behind on the linear-path trajectory."""
    behind = df[df["Delivery RAG"] == "Red"].copy()
    cols = ["Company Name", "ASX Code", "Cohort", CANON["near_term_status"],
            "Required Reduction % (now)", "Actual Reduction % (now)",
            "Gap to Path (pp)"]
    cols = [c for c in cols if c in behind.columns]
    behind = behind[cols].sort_values("Gap to Path (pp)", ascending=True)
    return {
        "title": f"Behind on delivery trajectory ({len(behind)} companies)",
        "summary": (
            "Actual S1+S2 reduction lags the linear path to their stated target by "
            "more than 10 pp. Highest-value BD conversation: 'you committed publicly, "
            "you're not on track, V2 is coming — let's get you back to the line.'"
        ),
        "table": behind,
        "table_caption": "Sorted by widest gap first (most behind).",
    }


def top_emitters_no_sbti(df: pd.DataFrame) -> dict:
    """Tier 1 companies with no validated SBTi target."""
    non_sbti = df[(df["SBTi"] == "No") & (df["ASRS Tier"] == "Tier 1")].copy()
    s1 = pd.to_numeric(non_sbti.get("NGER Scope 1 (tCO2e)"), errors="coerce").fillna(0)
    non_sbti["S1 (Mt)"] = (s1 / 1e6).round(2)
    non_sbti = non_sbti[non_sbti["S1 (Mt)"] > 0.5].sort_values("S1 (Mt)", ascending=False)
    cols = ["Company Name", "ASX Code", "Cohort", CANON["sector"], "S1 (Mt)",
            "Target Classification"]
    cols = [c for c in cols if c in non_sbti.columns]
    return {
        "title": f"Tier-1 emitters without SBTi targets ({len(non_sbti)} companies > 0.5 Mt)",
        "summary": (
            "Material direct emitters that haven't validated an SBTi target. "
            "Under ASRS Group 1 disclosure obligation but without the structured "
            "target framework. Conversation: 'mandatory reporting needs a credible "
            "target story — let's build it before stakeholders ask why you don't have one.'"
        ),
        "table": non_sbti[cols].head(30),
        "table_caption": "Top 30 by Scope 1. Tier 1 only.",
    }


def aspirational_only(df: pd.DataFrame) -> dict:
    """Companies whose only climate commitment is 'aspirational' / net-zero only."""
    asp = df[df["Target Classification"].isin(["Aspirational", "Net-zero only"])].copy()
    cols = ["Company Name", "ASX Code", "Cohort", "ASRS Tier", CANON["sector"],
            "Target Classification", CANON["net_zero_year"]]
    cols = [c for c in cols if c in asp.columns]
    asp = asp[cols].sort_values(["ASRS Tier", "Company Name"])
    return {
        "title": f"Aspirational-only commitments ({len(asp)} companies)",
        "summary": (
            "Have publicly stated 'net zero by 20XX' but haven't quantified the "
            "interim pathway. Strong BD signal: they've committed publicly, ASRS "
            "Tier 1/2 disclosure requires a credible plan, but they don't have one. "
            "Highest BD value with Tier 1 entries here."
        ),
        "table": asp.head(40),
        "table_caption": "Top 40 by tier then alphabetical. Filter to Tier 1 for material clients.",
    }


def imminent_target_year(df: pd.DataFrame) -> dict:
    """Companies with target year in the next 0-3 years — about to face the music."""
    yrs = pd.to_numeric(df["Years to Target"], errors="coerce")
    soon = df[(yrs >= 0) & (yrs <= 3)].copy()
    cols = ["Company Name", "ASX Code", "Cohort", CANON["near_term_status"],
            "Target Year (used)", "Years to Target", "Delivery RAG"]
    cols = [c for c in cols if c in soon.columns]
    soon = soon[cols].sort_values("Years to Target")
    return {
        "title": f"Target year imminent — within 3 years ({len(soon)} companies)",
        "summary": (
            "Targets due 2025-2028. Outcome visible within the BD cycle. "
            "Conversation pivots from 'how to commit' to 'how to deliver / "
            "what to communicate when the number lands'."
        ),
        "table": soon,
        "table_caption": "Sorted by closest target year first.",
    }


def asx_listed_committed_only(df: pd.DataFrame) -> dict:
    """ASX-listed companies that submitted SBTi intent but haven't validated yet."""
    sub = df[
        (df["ASX Listed"] == "Yes")
        & (df[CANON["near_term_status"]].astype(str).str.lower().str.contains("committed", na=False))
        & (~df[CANON["near_term_status"]].astype(str).str.lower().str.contains("removed", na=False))
        & (~df[CANON["near_term_status"]].astype(str).str.lower().str.contains("targets set", na=False))
    ].copy()
    cols = ["Company Name", "ASX Code", CANON["sector"], CANON["date_committed"],
            "ASRS Tier"]
    cols = [c for c in cols if c in sub.columns]
    return {
        "title": f"ASX-listed, SBTi committed but not yet validated ({len(sub)} companies)",
        "summary": (
            "Intent letter submitted to SBTi but the 24-month validation clock "
            "hasn't ticked yet (or is about to expire). Validate or withdraw — "
            "either way they need help. Public ASX visibility creates urgency."
        ),
        "table": sub[cols].sort_values("Company Name"),
        "table_caption": "Sorted A–Z. SBTi validation deadline = commitment + ~24 months.",
    }


# ─── Registry ────────────────────────────────────────────────────────────────

INSIGHTS = {
    "Top 10 BD targets": top_bd_targets,
    "Behind on delivery trajectory": behind_on_delivery,
    "SBTi commitment removed (re-engagement)": sbti_commitment_removed,
    "ASX-listed SBTi committed but not validated": asx_listed_committed_only,
    "Tier-1 emitters without SBTi target": top_emitters_no_sbti,
    "Aspirational-only commitments": aspirational_only,
    "Target year imminent (≤3 yrs)": imminent_target_year,
}
