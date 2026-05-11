"""Company Brief — free, local replacement for Ask Gus.

Generates a single, copy-paste-ready BD briefing for any company in the
cohort using only data already in the repo (SBTi, NGER, research overlay,
emissions cache, delivery math, TPI). No API calls, no cost.
"""

from __future__ import annotations

import pandas as pd

from modules.sbti import CANON


def _fmt_int(v) -> str:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        return f"{int(float(v)):,}"
    except (TypeError, ValueError):
        return str(v) or "—"


def _fmt_yr(v) -> str:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        return str(int(float(v)))
    except (TypeError, ValueError):
        return str(v) or "—"


def _fmt_str(v) -> str:
    if v is None:
        return "—"
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "n/a"):
        return "—"
    return s


def _section(title: str, body: str) -> str:
    return f"### {title}\n\n{body}\n"


def build_brief(rec: pd.Series, emissions_cache: dict | None = None) -> str:
    """Return a markdown brief for one company row."""
    company = _fmt_str(rec.get(CANON["company"]))
    asx = _fmt_str(rec.get("ASX Code"))
    sector = _fmt_str(rec.get(CANON["sector"]))
    cohort = _fmt_str(rec.get("Cohort"))
    tier = _fmt_str(rec.get("ASRS Tier"))
    listed = _fmt_str(rec.get("ASX Listed"))

    nt = _fmt_str(rec.get(CANON["near_term_status"]))
    lt = _fmt_str(rec.get(CANON["long_term_status"]))
    nz = _fmt_str(rec.get(CANON["net_zero_status"]))
    classification = _fmt_str(rec.get("Target Classification"))
    target_year = _fmt_yr(rec.get("Target Year (used)"))
    nz_year = _fmt_yr(rec.get(CANON["net_zero_year"]))
    yrs_to = _fmt_str(rec.get("Years to Target"))
    ambition = rec.get("Ambition % (parsed)")
    ambition_str = f"{int(ambition)}%" if pd.notna(ambition) else "—"
    target_wording = _fmt_str(rec.get(CANON["target"]))
    guidance = _fmt_str(rec.get("Applicable SBTi Guidance"))
    scopes = _fmt_str(rec.get("Target Scopes Covered"))

    base_year = _fmt_yr(rec.get("Base Year (used)"))
    latest_yr = _fmt_yr(rec.get("Latest Reported Year"))
    req_now = rec.get("Required Reduction % (now)")
    act_now = rec.get("Actual Reduction % (now)")
    gap = rec.get("Gap to Path (pp)")
    rag = _fmt_str(rec.get("Delivery RAG"))
    req_str = f"{req_now:.1f}%" if pd.notna(req_now) else "—"
    act_str = f"{act_now:.1f}%" if pd.notna(act_now) else "—"
    gap_str = f"{gap:+.1f} pp" if pd.notna(gap) else "—"

    s1 = _fmt_int(rec.get("Latest Scope 1 (tCO2e)"))
    s2 = _fmt_int(rec.get("Latest Scope 2 (tCO2e)"))
    s3 = _fmt_int(rec.get("Latest Scope 3 (tCO2e)"))
    nger_s1 = _fmt_int(rec.get("NGER Scope 1 (tCO2e)"))

    mq = _fmt_str(rec.get("MQ Description") or rec.get("MQ Level"))
    cp = _fmt_str(rec.get("CP Alignment"))

    v2 = _fmt_str(rec.get("V2 Reset Likely"))
    v2_reasons = _fmt_str(rec.get("V2 Reset Reasons"))

    scope3_status = _fmt_str(rec.get("Scope 3 Status"))
    recent_update = _fmt_str(rec.get("Recent Update"))
    bd_signals = _fmt_str(rec.get("BD Signals"))
    research_notes = _fmt_str(rec.get("Research Notes"))
    source_url = _fmt_str(rec.get("Research Source URL"))

    # ── Header
    header = f"# {company}"
    sub = f"**{asx}** · {sector} · ASRS {tier} · {'ASX-listed' if listed == 'Yes' else 'unlisted/private'} · {cohort}"

    # ── Headline (BD framing — derived from data)
    headline_bits = []
    if rag == "Red":
        headline_bits.append(f"⚠️ **Behind delivery path by {gap_str}** — required {req_str}, actual {act_str}.")
    elif rag == "Green":
        headline_bits.append(f"✅ On or ahead of path ({gap_str}).")
    elif rag == "Amber":
        headline_bits.append(f"🟡 Slightly behind path ({gap_str}).")
    if "removed" in nt.lower():
        headline_bits.append("🔻 **SBTi commitment removed** — re-engagement opportunity.")
    elif "committed" in nt.lower() and "set" not in nt.lower():
        headline_bits.append("📝 SBTi intent letter submitted — validation clock running.")
    elif "targets set" in nt.lower():
        headline_bits.append("✓ SBTi target validated.")
    if v2 == "Yes":
        headline_bits.append(f"🔄 **V2 reset likely** — {v2_reasons}")
    try:
        if yrs_to != "—" and int(float(yrs_to)) <= 3 and int(float(yrs_to)) >= 0:
            headline_bits.append(f"⏰ **Target year imminent** ({target_year} — {yrs_to} yr left).")
        elif yrs_to != "—" and int(float(yrs_to)) < 0:
            headline_bits.append(f"⏳ **Target year already passed** ({target_year}).")
    except (TypeError, ValueError):
        pass

    headline = "\n".join(f"- {b}" for b in headline_bits) if headline_bits else "_No specific BD flags from the data._"

    # ── Target
    target_block = (
        f"- **Near-term status:** {nt}\n"
        f"- **Long-term status:** {lt}\n"
        f"- **Net-zero status:** {nz}\n"
        f"- **Classification:** {classification}\n"
        f"- **Target year:** {target_year}  ·  **Net-zero year:** {nz_year}  ·  **Yrs to target:** {yrs_to}\n"
        f"- **Committed reduction:** {ambition_str}\n"
        f"- **SBTi guidance applicable:** {guidance}\n"
        f"- **Scopes covered:** {scopes}\n"
        f"- **Full target wording:**  \n> {target_wording}"
    )

    # ── Delivery
    delivery_block = (
        f"- **Base year:** {base_year}  ·  **Latest reported year:** {latest_yr}\n"
        f"- **Required reduction now (linear path):** {req_str}\n"
        f"- **Actual reduction now:** {act_str}\n"
        f"- **Gap to path:** {gap_str}  ·  **RAG:** {rag}"
    )

    # ── Emissions
    emissions_block = (
        f"- **Latest S1:** {s1} tCO2e\n"
        f"- **Latest S2:** {s2} tCO2e\n"
        f"- **Latest S3:** {s3} tCO2e\n"
        f"- **NGER S1 (regulator-reported):** {nger_s1} tCO2e"
    )

    # ── TPI
    tpi_block = (
        f"- **TPI Management Quality:** {mq}\n"
        f"- **TPI Carbon Performance alignment:** {cp}"
    )

    # ── Research / BD signals (only render if any data present)
    research_lines = []
    if scope3_status != "—":
        research_lines.append(f"- **Scope 3 status:** {scope3_status}")
    if recent_update != "—":
        research_lines.append(f"- **Recent update:** {recent_update}")
    if bd_signals != "—":
        research_lines.append(f"- **BD signals:** {bd_signals}")
    if research_notes != "—":
        research_lines.append(f"- **Research notes:** {research_notes}")
    if source_url != "—":
        research_lines.append(f"- **Source:** {source_url}")
    research_block = "\n".join(research_lines) if research_lines else "_No researched BD signals on file for this company._"

    # ── Emissions history (if cache has it)
    history_block = ""
    if emissions_cache:
        isin_key = str(rec.get(CANON["isin"], "")).strip().upper()
        cache_rec = emissions_cache.get(isin_key) or emissions_cache.get(company)
        if cache_rec and cache_rec.get("history"):
            hist = sorted(cache_rec["history"], key=lambda h: h.get("year", 0))
            rows = []
            for h in hist[-6:]:
                rows.append(
                    f"| {h.get('year', '—')} "
                    f"| {_fmt_int(h.get('s1'))} "
                    f"| {_fmt_int(h.get('s2'))} "
                    f"| {_fmt_int(h.get('s3'))} "
                    f"| {h.get('source', '—')} |"
                )
            if rows:
                history_block = (
                    "| Year | S1 | S2 | S3 | Source |\n"
                    "|------|----|----|----|--------|\n"
                    + "\n".join(rows)
                )

    parts = [
        header,
        sub,
        "",
        _section("BD headline", headline),
        _section("Target", target_block),
        _section("Delivery vs committed trajectory", delivery_block),
        _section("Latest emissions", emissions_block),
        _section("TPI-style indicators", tpi_block),
        _section("Research & BD signals", research_block),
    ]
    if history_block:
        parts.append(_section("Emissions history (last 6 years)", history_block))

    return "\n".join(parts)
