"""Ask Gus — live AI Q&A grounded in the cohort.

Builds a compact context summary of the cohort + key BD signals and calls
Claude with the user's question. Designed for short, BD-flavoured answers in
Gus's voice: direct, opinionated, no hedging.

Requires an Anthropic API key. Set via Streamlit secrets:
    [anthropic]
    api_key = "sk-ant-..."
or via env var ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import os
from typing import Iterator

import pandas as pd

try:
    import anthropic
except ImportError:
    anthropic = None  # checked at call time

from modules.sbti import CANON


MODEL_ID = "claude-opus-4-7"


SYSTEM_PROMPT_PREAMBLE = """You are Gus — a senior climate-strategy BD lead at Pollination, an Australian climate advisory firm. You speak directly, with opinions and a point of view. You sound like a consultant briefing a partner: short paragraphs, no corporate hedging, no bullet-point soup unless the question genuinely calls for a list.

You're answering questions for a Pollination BD colleague who has the cohort dataset open in front of them. They can see the table. Your job is to add the judgement layer: who matters, why now, what to say.

Style rules:
- 3–6 short sentences for most questions. Lists only when the user asks for a list or a ranking.
- Name specific companies — never "many companies" or "the cohort". If you can't name names, say you don't have the data.
- Lead with the BD angle: strategic moment + credibility gap + likely advisory wedge.
- If a company has both an SBTi target and a delivery gap, that's the wedge — say so.
- If asked something the data can't answer, say so plainly and suggest what would close the gap.
- Never invent numbers, target years, or commitments. If the cohort context below doesn't have it, say "not in the dataset I have."

You are NOT a generic climate analyst. You are a BD lead who knows this exact cohort and is helping a colleague figure out where to spend their next quarter."""


def _format_companies(rows: list[dict], max_n: int = 25) -> str:
    if not rows:
        return "  (none)"
    out = []
    for r in rows[:max_n]:
        parts = [r.get("name", "")]
        if r.get("asx"):
            parts.append(f"({r['asx']})")
        if r.get("sector"):
            parts.append(f"— {r['sector']}")
        meta = []
        for k in ("sbti_status", "target_year", "tier", "delivery", "s1_mt", "bd_signal"):
            v = r.get(k)
            if v not in (None, "", "nan") and not (isinstance(v, float) and pd.isna(v)):
                meta.append(f"{k}={v}")
        line = " ".join(parts)
        if meta:
            line += "  [" + "; ".join(meta) + "]"
        out.append("  • " + line)
    if len(rows) > max_n:
        out.append(f"  …({len(rows) - max_n} more)")
    return "\n".join(out)


def build_context(df: pd.DataFrame) -> str:
    """Build a static, cache-friendly cohort summary. Same content every call
    so Anthropic's prompt cache can serve it for free after the first request."""
    if df.empty:
        return "Cohort is empty — no data loaded."

    n = len(df)
    sbti_yes = int((df.get("SBTi", "") == "Yes").sum())
    tier1 = int((df.get("ASRS Tier", "") == "Tier 1").sum())
    asx_listed = int((df.get("ASX Listed", "") == "Yes").sum())

    nt_status = df[CANON["near_term_status"]].astype(str).str.lower()
    n_validated = int(nt_status.str.contains("targets set", na=False).sum())
    n_committed = int(nt_status.str.contains("committed", na=False).sum()
                      - nt_status.str.contains("removed", na=False).sum())
    n_removed = int(nt_status.str.contains("removed", na=False).sum())

    red = int((df.get("Delivery RAG", "") == "Red").sum())
    amber = int((df.get("Delivery RAG", "") == "Amber").sum())
    green = int((df.get("Delivery RAG", "") == "Green").sum())

    # Top emitters (Scope 1) — most BD-relevant for the heavy-industry conversation
    s1 = pd.to_numeric(df.get("NGER Scope 1 (tCO2e)"), errors="coerce").fillna(0)
    top_s1 = df.assign(_s1=s1).nlargest(20, "_s1")
    top_s1_rows = [
        {
            "name": r[CANON["company"]],
            "asx": r.get("ASX Code"),
            "sector": r.get(CANON["sector"]),
            "sbti_status": r.get(CANON["near_term_status"]) or "—",
            "s1_mt": round(r["_s1"] / 1e6, 2),
            "tier": r.get("ASRS Tier"),
        }
        for _, r in top_s1.iterrows() if r["_s1"] > 0
    ]

    # Behind-on-delivery (Red)
    behind = df[df.get("Delivery RAG", "") == "Red"].copy()
    behind_rows = [
        {
            "name": r[CANON["company"]],
            "asx": r.get("ASX Code"),
            "sector": r.get(CANON["sector"]),
            "sbti_status": r.get(CANON["near_term_status"]),
            "target_year": r.get("Target Year (used)"),
            "delivery": f"gap {r.get('Gap to Path (pp)', '?')} pp",
        }
        for _, r in behind.iterrows()
    ]

    # SBTi commitment removed
    removed = df[nt_status.str.contains("removed", na=False)].copy()
    removed_rows = [
        {
            "name": r[CANON["company"]],
            "asx": r.get("ASX Code"),
            "sector": r.get(CANON["sector"]),
            "sbti_status": r.get(CANON["near_term_status"]),
        }
        for _, r in removed.iterrows()
    ]

    # Imminent target year (≤3 yrs)
    yrs = pd.to_numeric(df.get("Years to Target"), errors="coerce")
    soon = df[(yrs >= 0) & (yrs <= 3)].copy()
    soon_rows = [
        {
            "name": r[CANON["company"]],
            "asx": r.get("ASX Code"),
            "target_year": r.get("Target Year (used)"),
            "delivery": r.get("Delivery RAG", "—"),
        }
        for _, r in soon.iterrows()
    ]

    # Tier 1 non-SBTi (mandatory ASRS, no SBTi target)
    nonsbti = df[(df.get("SBTi", "") == "No") & (df.get("ASRS Tier", "") == "Tier 1")].copy()
    nonsbti_s1 = pd.to_numeric(nonsbti.get("NGER Scope 1 (tCO2e)"), errors="coerce").fillna(0)
    nonsbti = nonsbti.assign(_s1=nonsbti_s1).nlargest(20, "_s1")
    nonsbti_rows = [
        {
            "name": r[CANON["company"]],
            "asx": r.get("ASX Code"),
            "sector": r.get(CANON["sector"]),
            "s1_mt": round(r["_s1"] / 1e6, 2),
        }
        for _, r in nonsbti.iterrows() if r["_s1"] > 0
    ]

    # BD signals from research metadata (where present)
    has_bd = df[df.get("BD Signals", "").astype(str).str.strip().ne("")].copy()
    bd_rows = [
        {
            "name": r[CANON["company"]],
            "bd_signal": str(r.get("BD Signals", ""))[:240],
        }
        for _, r in has_bd.iterrows()
    ]

    sectors = (
        df[CANON["sector"]].value_counts().head(12).to_dict()
        if CANON["sector"] in df.columns else {}
    )
    sector_str = "; ".join(f"{k} ({v})" for k, v in sectors.items())

    parts = [
        "# Cohort context (Australia, current snapshot)",
        "",
        "## Headline counts",
        f"- Total companies in cohort: {n}",
        f"- ASX-listed: {asx_listed}",
        f"- With an SBTi entry: {sbti_yes}  (validated={n_validated}, committed={n_committed}, removed={n_removed})",
        f"- ASRS Tier 1 (AASB S2 mandatory disclosure, Group 1): {tier1}",
        f"- Delivery vs linear path: {green} Green / {amber} Amber / {red} Red (Red = >10pp behind)",
        "",
        f"## Sector mix (top 12)",
        f"  {sector_str or '(none)'}",
        "",
        "## Top 20 Scope 1 emitters (Mt CO2e, NGER 2024–25)",
        _format_companies(top_s1_rows),
        "",
        "## Behind on delivery trajectory (Red — actual >10pp below required)",
        _format_companies(behind_rows, max_n=40),
        "",
        "## SBTi commitment removed (intent letter withdrawn or expired)",
        _format_companies(removed_rows, max_n=40),
        "",
        "## Target year imminent (within 3 years)",
        _format_companies(soon_rows, max_n=40),
        "",
        "## Tier 1 emitters without an SBTi target",
        _format_companies(nonsbti_rows),
        "",
        "## Companies with researched BD signals (recent strategic moments)",
        _format_companies(bd_rows, max_n=60),
        "",
        "## Curated top-10 BD priority list (hand-selected — strategic moment + credibility gap)",
        "  1. Pioneer Sail Holdings — Sembcorp $4.3bn acquisition pending Dec 2025; 2.7Mt 2030 group target acknowledged unachievable post-Alinta",
        "  2. EnergyAustralia — May 2025 greenwashing case settled with Parents for Climate; ACCU/offset strategy under review; Yallourn closure 2028",
        "  3. Stanwell — AU #1 NGER S1 emitter (17.9Mt); no entity SBTi; LNP government reviewing QEJP",
        "  4. Woodside — 58% shareholder rejection of CTAP at 2024 AGM; Aug 2025 Woodside-Santos merger pending; SBTi withdrawn",
        "  5. Chevron Australia — Gorgon CCS underperforming (~30–40% vs design); ACCU/Safeguard exposure; foreign-parent ASRS complexity",
        "  6. Fortescue — Real Zero S1+S2 by 2030 (most aggressive in cohort); publicly rejected SBTi 2024; $6.2bn capex committed",
        "  7. BHP — largest miner; SBTi committed but not validated; recently divested Blackwater/Daunia; growing S3 product-use scrutiny",
        "  8. Coles — SBTi-validated 75% S1+S2 by FY35 (most ambitious retail target); Scope 3 supplier engagement at scale",
        "  9. AGL — coal exit 2035 accelerated from 2045; 78% S1+S2 reduction by FY34–35; 5GW+ renewables pipeline",
        " 10. Origin — 60% S1+S2+S3 by 2035 from FY17 (ratchet-up); Eraring closure delayed to 2027; SBTi pre-validation",
    ]
    return "\n".join(parts)


def get_client() -> "anthropic.Anthropic | None":
    """Resolve the Anthropic API key from Streamlit secrets or env."""
    if anthropic is None:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("anthropic", {}).get("api_key") if hasattr(st, "secrets") else None
        except Exception:
            key = None
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def stream_answer(
    client: "anthropic.Anthropic",
    context: str,
    history: list[dict],
    question: str,
) -> Iterator[str]:
    """Yield text deltas from Claude as they arrive. `history` is the running
    list of prior {role, content} pairs (assistant + user turns)."""
    system = [
        {"type": "text", "text": SYSTEM_PROMPT_PREAMBLE},
        {
            "type": "text",
            "text": context,
            "cache_control": {"type": "ephemeral"},
        },
    ]
    messages = list(history) + [{"role": "user", "content": question}]

    with client.messages.stream(
        model=MODEL_ID,
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
