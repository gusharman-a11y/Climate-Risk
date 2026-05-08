"""ASX SBTi BD tracker — target screen, delivery, TPI-style indicators.

Run: streamlit run sbti_tracker.py
"""

from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.sbti import CANON, DATA_DIR, load_sbti
from modules.sbti_phase1 import (
    COHORTS,
    DISPLAY_COLS,
    SECTOR_RULES,
    V2_COLOUR,
    build_all,
    build_screen,
)
from modules.phase2 import (
    DELIVERY_COLOUR,
    build_delivery,
    csv_template_bytes,
    load_cache,
    merge_csv,
    save_cache,
    upsert_record,
)
from modules.scraper import (
    fetch_and_parse,
    fetch_pdf,
    load_stored_urls,
    lookup_stored_url,
    parse_emissions,
    search_report_url,
)
from modules.tpi import MQ_COLOUR, CP_COLOUR, attach_tpi


def _column_config():
    """Centralised column display rules: friendly names + integer year format."""
    yr = st.column_config.NumberColumn(format="%d")
    return {
        "MQ Level": st.column_config.TextColumn(
            "Climate maturity",
            help="TPI Management Quality (0–4*). 0 unaware → 4* aligned strategic. "
                 "Synthesised from SBTi disclosures.",
        ),
        "CP Alignment": st.column_config.TextColumn(
            "Carbon Performance",
            help="TPI alignment label: 1.5°C / Below 2°C / 2°C / Not aligned / Insufficient.",
        ),
        "Target Year (used)": st.column_config.NumberColumn("Target Year", format="%d"),
        "Years to Target": st.column_config.NumberColumn("Yrs to target", format="%d"),
        "Latest Reported Year": yr,
        "Target Year": yr,
        "Net-Zero Year": yr,
        "Long-term Target Year": yr,
        "Base Year": yr,
        "Ambition % (parsed)": st.column_config.NumberColumn(
            "Committed reduction %",
            format="%.0f %%",
            help="The % reduction the company committed to in its SBTi target — "
                 "e.g. '50% by 2030 from a 2019 base year' → 50%. Parsed from the "
                 "full target wording.",
        ),
        "Required Reduction % (now)": st.column_config.NumberColumn(
            "Required reduction now",
            format="%.1f %%",
            help="What % reduction the company should have achieved by the latest "
                 "reporting year, on a straight-line path from base year to target year.",
        ),
        "Actual Reduction % (now)": st.column_config.NumberColumn(
            "Actual reduction now",
            format="%.1f %%",
            help="Reduction actually achieved at the latest reporting year, vs the base year.",
        ),
        "Gap to Path (pp)": st.column_config.NumberColumn(
            "Gap to path",
            format="%+.1f pp",
            help="Actual − Required. Positive = ahead of path. Negative = behind.",
        ),
    }


st.set_page_config(
    page_title="ASX SBTi BD tracker",
    page_icon="🇦🇺",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
[data-testid="stSidebar"] { background-color: #0F172A; }
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
.v2-Yes { color: #DC2626; font-weight: 700; }
.v2-No  { color: #16A34A; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)


# ─── Sidebar: data load ────────────────────────────────────────────────────────
st.sidebar.title("🇦🇺 ASX SBTi BD tracker")
st.sidebar.caption("Target adequacy, V2 reset risk, delivery progress")

with st.sidebar.expander("📁 Data sources", expanded=False):
    sbti_upload = st.file_uploader(
        "SBTi Companies-Taking-Action (CSV/XLSX)",
        type=["csv", "xlsx", "xls"],
        help="Override the bundled SBTi data with a fresh download.",
    )


@st.cache_data(show_spinner=False)
def _load(file_bytes: bytes | None, name: str | None):
    if file_bytes is None:
        return load_sbti(None)
    buf = io.BytesIO(file_bytes)
    buf.name = name or "upload.csv"
    return load_sbti(buf)


sbti_df = _load(
    sbti_upload.getvalue() if sbti_upload else None,
    sbti_upload.name if sbti_upload else None,
)

if sbti_df.empty:
    st.title("🇦🇺 ASX SBTi BD tracker")
    st.warning(
        f"No SBTi data loaded. Upload the **Companies Taking Action** dataset from "
        f"the sidebar, or commit it to `{DATA_DIR / 'sbti_companies.xlsx'}`."
    )
    st.stop()

screen = build_all(sbti_df)

emissions_cache = load_cache()

with st.sidebar.expander("📊 Reported emissions", expanded=False):
    emissions_csv = st.file_uploader(
        "Bulk upload emissions CSV",
        type=["csv"],
        help="Use the template below for batch ingest.",
    )
    if emissions_csv is not None:
        try:
            n = merge_csv(emissions_cache, emissions_csv.getvalue())
            save_cache(emissions_cache)
            st.success(f"Merged {n} rows.")
        except Exception as exc:
            st.error(f"Merge failed: {exc}")

    st.download_button(
        "📥 Download CSV template",
        csv_template_bytes(),
        file_name="emissions_template.csv",
        mime="text/csv",
    )

    # Persist whatever's in the runtime cache by downloading + committing.
    import json as _json
    cache_payload = _json.dumps(emissions_cache, indent=2, default=str).encode("utf-8")
    n_companies = len(emissions_cache)
    n_records = sum(len(rec.get("history", [])) for rec in emissions_cache.values())
    st.download_button(
        f"💾 Download emissions cache ({n_companies} companies, {n_records} entries)",
        cache_payload,
        file_name="emissions_cache.json",
        mime="application/json",
        help=(
            "After running 'Fetch + parse all stored reports', download this file "
            "and paste its contents (or upload it) to Claude in chat — Claude commits "
            "it to the repo so the data persists permanently for the team."
        ),
    )

stored_urls = load_stored_urls()
if stored_urls:
    with st.sidebar.expander(f"🌐 Stored report URLs ({len(stored_urls)})", expanded=False):
        st.caption(
            "Curated sustainability-report PDF URLs for the cohort. "
            "Click 'Fetch all' to download + parse each report and populate "
            "the emissions cache. Runs on this server's network."
        )
        if st.button("⚡ Fetch + parse all stored reports"):
            progress = st.progress(0.0)
            log_box = st.empty()
            successes, failures = [], []
            n = len(stored_urls)
            for i, rec in enumerate(stored_urls, start=1):
                progress.progress(i / n, text=f"{i}/{n} {rec['company']}")
                try:
                    parsed = fetch_and_parse(rec["url"])
                    if "error" in parsed:
                        failures.append((rec["company"], parsed["error"]))
                        continue
                    if not parsed.get("reporting_year"):
                        failures.append((rec["company"], "no reporting year detected"))
                        continue
                    upsert_record(
                        emissions_cache,
                        company=rec["company"], isin=None,
                        reporting_year=int(parsed["reporting_year"]),
                        s1=parsed.get("s1"), s2=parsed.get("s2"), s3=parsed.get("s3"),
                        source="auto-fetched",
                        source_url=rec["url"],
                    )
                    successes.append(rec["company"])
                except Exception as exc:
                    failures.append((rec["company"], str(exc)[:120]))
            save_cache(emissions_cache)
            log_box.success(f"Fetched: {len(successes)} / {n}. Reload the page to refresh the table.")
            if failures:
                with log_box.container():
                    st.error(f"Failed: {len(failures)}")
                    for c, e in failures:
                        st.caption(f"• {c}: {e}")

screen = build_delivery(screen, emissions_cache)
screen = attach_tpi(screen)


# ─── Title (filters render below) ─────────────────────────────────────────────
st.title(f"🇦🇺 ASX SBTi BD tracker")
st.caption(
    "All Australian-listed and large private SBTi companies, plus ASX 200 companies "
    "without SBTi targets. Use the cohort and ASRS Tier filters to slice."
)

# ─── Top filter bar (horizontal) ──────────────────────────────────────────────
sectors = sorted([s for s in screen[CANON["sector"]].dropna().unique() if str(s).strip()])
cohort_options = [c for c in COHORTS.keys() if c in screen["Cohort"].unique()]
asrs_tiers_present = [t for t in ["Tier 1", "Tier 1 (proxy)", "Tier 2", "Tier 2 (proxy)", "Tier 3", "Unclassified"]
                      if t in screen.get("ASRS Tier", pd.Series(dtype=str)).unique()]

with st.container(border=True):
    st.caption("**Filters** — change any to narrow the view; defaults show all companies.")
    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 2, 2, 1])
    with fcol1:
        f_cohort = st.multiselect(
            "Cohort",
            cohort_options,
            default=[],
            key="ftr_cohort",
            help=(
                "ASX listed (SBTi) — validated SBTi targets. "
                "Australian Corporate / FI (SBTi, private) — SBTi private cos. "
                "ASX 200 — no SBTi target — ASX-listed without SBTi."
            ),
        )
    with fcol2:
        f_tier = st.multiselect(
            "AASB S2 / ASRS reporting tier",
            asrs_tiers_present,
            default=[],
            key="ftr_tier",
            help=(
                "Per AASB S2 Climate-related Disclosures (the Australian ISSB-aligned standard).\n\n"
                "**Tier 1**: meets ≥2 of A$500M revenue / A$1B assets / 500 employees.\n"
                "**Tier 2**: meets ≥2 of A$200M / A$500M / 250.\n"
                "**Tier 3**: meets ≥2 of A$50M / A$25M / 100.\n\n"
                "**(proxy)** = revenue/assets/employees not on file; tier inferred "
                "from market cap tier or SBTi Org Type."
            ),
        )
    with fcol3:
        search = st.text_input("🔍 Search by company name", key="ftr_search")
    with fcol4:
        if st.button("↻ Clear filters", use_container_width=True):
            for k in ("ftr_search", "ftr_sector", "ftr_priority", "ftr_yrs",
                      "ftr_mq", "ftr_cp", "ftr_delivery", "ftr_cohort", "ftr_tier"):
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    with st.expander("More filters", expanded=False):
        gcol1, gcol2, gcol3, gcol4 = st.columns(4)
        with gcol1:
            f_sector = st.multiselect("Sector", sectors, key="ftr_sector")
            f_priority = st.radio(
                "Outreach priority",
                ["All", "High (target ≤2030 or scope gap)", "Low (target >2030 and on track)"],
                index=0, key="ftr_priority",
                help="High = target year ≤2030, target year passed, or required scopes missing.",
            )
        with gcol2:
            f_yrs = st.slider(
                "Years to target",
                min_value=-10, max_value=30, value=(-10, 30), step=1,
                key="ftr_yrs",
                help="Negative = target year already passed.",
            )
            f_mq = st.multiselect(
                "Climate maturity (TPI MQ)",
                ["0", "1", "2", "3", "4", "4*"],
                key="ftr_mq",
            )
        with gcol3:
            f_cp = st.multiselect(
                "CP Alignment",
                ["Aligned 1.5°C", "Aligned Below 2°C", "Aligned 2°C / NDC",
                 "Not aligned", "Insufficient disclosure"],
                key="ftr_cp",
            )
        with gcol4:
            f_delivery = st.multiselect(
                "Delivery RAG",
                ["Green", "Amber", "Red", "N/A"],
                key="ftr_delivery",
            )

# Track active filters for chip display
active_filters: list[str] = []

filtered = screen.copy()
total_in_cohort = len(filtered)

if f_cohort:
    filtered = filtered[filtered["Cohort"].isin(f_cohort)]
    active_filters.append(f"Cohort: {len(f_cohort)} selected")
if f_tier:
    filtered = filtered[filtered.get("ASRS Tier", pd.Series([""] * len(filtered))).isin(f_tier)]
    active_filters.append(f"ASRS Tier: {', '.join(f_tier)}")
if search:
    filtered = filtered[filtered[CANON["company"]].str.contains(search, case=False, na=False)]
    active_filters.append(f"Search: \"{search}\"")
if f_sector:
    filtered = filtered[filtered[CANON["sector"]].isin(f_sector)]
    active_filters.append(f"Sector: {len(f_sector)} selected")
if f_priority == "High (target ≤2030 or scope gap)":
    filtered = filtered[filtered["V2 Reset Likely"] == "Yes"]
    active_filters.append("Outreach: High priority only")
elif f_priority == "Low (target >2030 and on track)":
    filtered = filtered[filtered["V2 Reset Likely"] == "No"]
    active_filters.append("Outreach: Low priority only")
yrs_lo, yrs_hi = f_yrs
if (yrs_lo, yrs_hi) != (-10, 30):
    mask = filtered["Years to Target"].between(yrs_lo, yrs_hi, inclusive="both")
    mask = mask | filtered["Years to Target"].isna()
    filtered = filtered[mask]
    active_filters.append(f"Years to target: {yrs_lo}…{yrs_hi}")
if f_mq:
    filtered = filtered[filtered["MQ Level"].isin(f_mq)]
    active_filters.append(f"MQ Level: {', '.join(f_mq)}")
if f_cp:
    filtered = filtered[filtered["CP Alignment"].isin(f_cp)]
    active_filters.append(f"CP Alignment: {len(f_cp)} selected")
if f_delivery:
    filtered = filtered[filtered["Delivery RAG"].isin(f_delivery)]
    active_filters.append(f"Delivery RAG: {', '.join(f_delivery)}")

# Active-filter chips + counter
if active_filters:
    chip_html = " ".join(
        f"<span style='display:inline-block; background:#1E40AF22; color:#1E40AF; "
        f"padding:2px 10px; border-radius:12px; font-size:0.82rem; "
        f"font-weight:500; margin-right:6px;'>{f}</span>"
        for f in active_filters
    )
    st.markdown(
        f"**Showing {len(filtered)} of {total_in_cohort} companies**  &nbsp; {chip_html}",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"**Showing all {total_in_cohort} companies in cohort** — no filters active."
    )


# ─── KPIs ────────────────────────────────────────────────────────────────────
total = len(filtered)
due_2030 = int((filtered["Target Year (used)"] <= 2030).fillna(False).sum())
expired = int((filtered["Years to Target"] < 0).fillna(False).sum())
high_priority = int((filtered["V2 Reset Likely"] == "Yes").sum())
aligned_15 = int((filtered["CP Alignment"] == "Aligned 1.5°C").sum())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Companies in view", f"{total:,}")
c2.metric("⏰ Target ≤2030", f"{due_2030:,}")
c3.metric("⏳ Target year passed", f"{expired:,}")
c4.metric("🎯 High outreach priority", f"{high_priority:,}")
c5.metric("✅ Aligned 1.5°C", f"{aligned_15:,}")


tab_screen, tab_delivery, tab_charts, tab_company, tab_rulebook = st.tabs(
    ["Cohort", "Delivery", "Sector view", "Company drill-down", "Sector rulebook"]
)


with tab_screen:
    st.markdown("### Cohort — ranked by target proximity")
    st.caption("Sorted by **Years to Target** ascending — most imminent first.")

    cols_present = [c for c in DISPLAY_COLS if c in filtered.columns]
    table = filtered[cols_present].copy()

    def _row_style(row):
        colour = V2_COLOUR.get(row["V2 Reset Likely"], "#FFFFFF")
        return [
            f"background-color: {colour}22; color: {colour}; font-weight: 600"
            if c == "V2 Reset Likely" else "" for c in row.index
        ]

    styler = table.style.apply(_row_style, axis=1)
    st.dataframe(styler, use_container_width=True, height=620, hide_index=True,
                 column_config=_column_config())

    st.download_button(
        "Download Phase 1 screen (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="asx_sbti_phase1_screen.csv",
        mime="text/csv",
    )

    bd1, bd2 = st.columns(2)
    with bd1:
        st.markdown("**Outreach list — looming targets (≤2030)**")
        bd1_df = (
            filtered[filtered["Target Year (used)"] <= 2030]
            [[CANON["company"], CANON["sector"], "Target Year (used)", "Years to Target",
              "Applicable SBTi Guidance"]]
            .sort_values("Years to Target")
        )
        st.dataframe(bd1_df, use_container_width=True, height=280, hide_index=True,
                     column_config=_column_config())
    with bd2:
        st.markdown("**Outreach list — V2 will force a target reset**")
        bd2_df = (
            filtered[filtered["V2 Reset Likely"] == "Yes"]
            [[CANON["company"], CANON["sector"], "V2 Reset Reasons"]]
        )
        st.dataframe(bd2_df, use_container_width=True, height=280, hide_index=True,
                     column_config=_column_config())


with tab_delivery:
    st.markdown("### Delivery against committed trajectory")
    st.caption(
        "Linear-path comparison from each company's own base year to its target year. "
        "Required reduction at the latest reporting year is "
        "(elapsed yrs / horizon yrs) × ambition %. **Gap-to-path (pp)** = actual − required. "
        "Positive = ahead of path."
    )

    has_data = filtered["Latest Reported Year"].notna()
    coverage = int(has_data.sum())
    total_in_view = len(filtered)
    g = int((filtered["Delivery RAG"] == "Green").sum())
    a = int((filtered["Delivery RAG"] == "Amber").sum())
    r = int((filtered["Delivery RAG"] == "Red").sum())
    n = int((filtered["Delivery RAG"] == "N/A").sum())

    cov_pct = (coverage / total_in_view * 100) if total_in_view else 0
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("With reported emissions", f"{coverage:,} / {total_in_view:,}", f"{cov_pct:.0f}% coverage")
    k2.metric("🟢 On / ahead of path", f"{g:,}")
    k3.metric("🟡 Behind ≤10pp", f"{a:,}")
    k4.metric("🔴 Behind >10pp", f"{r:,}")
    k5.metric("⚪ No data yet", f"{n:,}")

    delivery_cols = [
        CANON["company"], CANON["sector"], "Applicable SBTi Guidance",
        "Base Year (used)", "Base S1+S2 (tCO2e)", "Latest Reported Year", "Latest S1+S2 (tCO2e)",
        "Ambition % (parsed)",
        "Required Reduction % (now)", "Actual Reduction % (now)",
        "Gap to Path (pp)", "Delivery RAG", "Data Source",
    ]
    delivery_cols = [c for c in delivery_cols if c in filtered.columns]
    sort_options = ["Gap to Path (pp)", "Years to Target", CANON["company"]]
    sort_by = st.selectbox("Sort by", sort_options, index=0)
    ascending = st.checkbox("Ascending (worst gap first)", value=True)

    table = filtered[delivery_cols].copy()
    if sort_by in table.columns:
        table = table.sort_values(sort_by, ascending=ascending, na_position="last")

    def _delivery_style(row):
        c = DELIVERY_COLOUR.get(row.get("Delivery RAG"), "#FFFFFF")
        return [
            f"background-color: {c}22; color: {c}; font-weight: 600"
            if col == "Delivery RAG" else "" for col in row.index
        ]

    st.dataframe(table.style.apply(_delivery_style, axis=1),
                 use_container_width=True, height=520, hide_index=True,
                 column_config=_column_config())
    st.download_button(
        "Download delivery table (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="asx_sbti_phase2_delivery.csv",
        mime="text/csv",
    )

    st.markdown(
        "**To populate emissions data:** bulk-upload the CSV template from the "
        "sidebar, or enter per-company in the **Company drill-down** tab "
        "(supports PDF upload, URL paste, and auto-search)."
    )


with tab_charts:
    st.markdown("### V2 reset distribution by SBTi sector guidance")
    rule_dist = (
        filtered.groupby(["Applicable SBTi Guidance", "V2 Reset Likely"])
        .size().reset_index(name="Companies")
    )
    if not rule_dist.empty:
        fig = px.bar(
            rule_dist, x="Applicable SBTi Guidance", y="Companies", color="V2 Reset Likely",
            color_discrete_map=V2_COLOUR, barmode="stack",
        )
        fig.update_layout(height=480, xaxis_tickangle=-30,
                          xaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Target-year profile")
    yr_df = filtered[filtered["Target Year (used)"].notna()].copy()
    if not yr_df.empty:
        yr_df["Year"] = yr_df["Target Year (used)"].astype(int)
        year_dist = (
            yr_df.groupby(["Year", "V2 Reset Likely"]).size().reset_index(name="Companies")
        )
        fig2 = px.bar(
            year_dist, x="Year", y="Companies", color="V2 Reset Likely",
            color_discrete_map=V2_COLOUR, barmode="stack",
        )
        fig2.update_layout(height=380, xaxis_dtick=1)
        fig2.add_vline(x=2030, line_dash="dash", line_color="#DC2626",
                       annotation_text="V2 horizon", annotation_position="top")
        st.plotly_chart(fig2, use_container_width=True)


with tab_company:
    st.markdown("### Company drill-down")
    if filtered.empty:
        st.info("No companies match the current filters.")
    else:
        company = st.selectbox(
            "Company", sorted(filtered[CANON["company"]].dropna().unique())
        )
        rec = filtered[filtered[CANON["company"]] == company].iloc[0]

        v2 = rec["V2 Reset Likely"]
        st.markdown(
            f"#### {company} &nbsp; <span class='v2-{v2}'>● V2 reset: {v2}</span>",
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Sector", str(rec.get(CANON["sector"], "—")))
        col2.metric("Target year",
                    "—" if pd.isna(rec["Target Year (used)"]) else int(rec["Target Year (used)"]))
        col3.metric(
            "Years to target",
            "—" if pd.isna(rec["Years to Target"]) else int(rec["Years to Target"]),
        )
        col4.metric("Year source", str(rec.get("Year Source", "—")))

        st.markdown(f"**Applicable SBTi guidance:** {rec['Applicable SBTi Guidance']}")
        st.markdown(f"**Target scopes covered:** {rec['Target Scopes Covered']}")

        if rec["V2 Reset Likely"] == "Yes":
            st.warning(f"**V2 reset reasons:** {rec['V2 Reset Reasons']}")

        if pd.notna(rec.get(CANON["target"])):
            st.markdown("**Full target language**")
            st.info(str(rec[CANON["target"]]))

        st.markdown("**Status detail**")
        detail = pd.DataFrame({
            "Field": [
                "Near-term status", "Long-term status", "Net-Zero status",
                "Classification (long)", "Date committed", "Date updated",
                "Removal/Extension reason",
            ],
            "Value": [
                rec.get(CANON["near_term_status"]), rec.get(CANON["long_term_status"]),
                rec.get(CANON["net_zero_status"]), rec.get(CANON["target_class_long"]),
                rec.get(CANON["date_committed"]), rec.get(CANON["date_updated"]),
                rec.get(CANON["removal_reason"]),
            ],
        })
        st.table(detail)

        # ── TPI-style indicators ──
        st.markdown("---")
        tpi_c1, tpi_c2 = st.columns(2)
        with tpi_c1:
            mq = rec.get("MQ Level", "0")
            mq_colour = MQ_COLOUR.get(mq, "#6B7280") if isinstance(mq, str) else MQ_COLOUR.get(int(mq) if str(mq).isdigit() else 0, "#6B7280")
            st.markdown(
                f"**Climate maturity (TPI Management Quality):** "
                f"<span style='color:{mq_colour}; font-weight:700'>"
                f"{rec.get('MQ Description', '—')}</span>",
                unsafe_allow_html=True,
            )
        with tpi_c2:
            cp = rec.get("CP Alignment", "—")
            cp_colour = CP_COLOUR.get(cp, "#6B7280")
            st.markdown(
                f"**Carbon Performance alignment (TPI):** "
                f"<span style='color:{cp_colour}; font-weight:700'>{cp}</span>",
                unsafe_allow_html=True,
            )
        st.caption(
            "MQ and CP indicators are derived from SBTi disclosures using TPI's "
            "framework structure. They are directional, not authoritative — TPI's "
            "own published assessments take precedence where available."
        )

        # ── Delivery against committed trajectory ──
        st.markdown("---")
        st.markdown("### Delivery against committed trajectory")

        d_col1, d_col2, d_col3, d_col4 = st.columns(4)
        d_col1.metric("Base year", "—" if pd.isna(rec.get("Base Year (used)")) else int(rec["Base Year (used)"]))
        d_col2.metric("Latest year", "—" if pd.isna(rec.get("Latest Reported Year")) else int(rec["Latest Reported Year"]))
        d_col3.metric(
            "Required reduction now",
            "—" if pd.isna(rec.get("Required Reduction % (now)")) else f"{rec['Required Reduction % (now)']}%",
        )
        gap = rec.get("Gap to Path (pp)")
        d_col4.metric(
            "Gap to path",
            "—" if pd.isna(gap) else f"{gap:+.1f} pp",
            delta="On/ahead" if (not pd.isna(gap) and gap >= 0) else ("Behind" if not pd.isna(gap) else None),
            delta_color="normal" if (pd.isna(gap) or gap >= 0) else "inverse",
        )

        rag = rec.get("Delivery RAG", "N/A")
        if rag == "Green":
            st.success(f"Delivery RAG: **Green** — actual reduction is at or above the linear path required by the committed target.")
        elif rag == "Amber":
            st.warning(f"Delivery RAG: **Amber** — behind path by {abs(gap):.1f} pp (≤10 pp).")
        elif rag == "Red":
            st.error(f"Delivery RAG: **Red** — behind path by {abs(gap):.1f} pp (>10 pp).")
        else:
            st.info("Delivery RAG: **N/A** — emissions data not yet entered. Use the form below.")

        # Trajectory chart if we have data
        isin_key = str(rec.get(CANON["isin"], "")).strip().upper()
        cache_rec = emissions_cache.get(isin_key) or emissions_cache.get(company)
        if cache_rec and cache_rec.get("history"):
            hist_df = pd.DataFrame(cache_rec["history"]).sort_values("year")
            hist_df["S1+S2"] = hist_df.apply(
                lambda r: (r.get("s1") or 0) + (r.get("s2") or 0)
                if (r.get("s1") is not None or r.get("s2") is not None) else None,
                axis=1,
            )
            base_year = cache_rec.get("base_year")
            base_s12 = cache_rec.get("base_s12")
            target_year = int(rec["Target Year (used)"]) if pd.notna(rec.get("Target Year (used)")) else None
            ambition = rec.get("Ambition % (parsed)")
            chart_data = hist_df[["year", "S1+S2"]].rename(columns={"year": "Year"}).copy()
            if base_year and base_s12 and target_year and ambition is not None and not pd.isna(ambition):
                req_path = pd.DataFrame({
                    "Year": [base_year, target_year],
                    "Required path (S1+S2)": [base_s12, base_s12 * (1 - float(ambition) / 100)],
                })
                chart_merged = chart_data.merge(req_path, on="Year", how="outer").sort_values("Year")
            else:
                chart_merged = chart_data
            st.markdown("**Emissions trajectory**")
            st.line_chart(chart_merged.set_index("Year"))
        else:
            st.caption("No reported emissions on file. Add via the form below or via CSV upload in the sidebar.")

        # ── Stored URL one-click fetch (if available) ──
        stored_url_rec = lookup_stored_url(company, isin_key, stored_urls)
        if stored_url_rec and stored_url_rec.get("url"):
            with st.container():
                st.info(
                    f"📎 **Curated report on file:** "
                    f"{stored_url_rec.get('report', 'Sustainability Report')} "
                    f"({stored_url_rec.get('period', '')})  \n"
                    f"[{stored_url_rec['url']}]({stored_url_rec['url']})"
                    + (f"  \n*Note:* {stored_url_rec['notes']}" if stored_url_rec.get("notes") else "")
                )

        # ── Three-layer ingestion: PDF upload, paste URL, auto-search ──
        st.markdown("#### Ingest sustainability report")
        ing_tab1, ing_tab2, ing_tab3 = st.tabs([
            "📄 Upload PDF (most reliable)", "🔗 Paste URL", "🔎 Auto-search"
        ])

        parsed_seed: dict | None = None
        seed_source = ""
        seed_url = stored_url_rec["url"] if stored_url_rec else ""

        with ing_tab1:
            st.caption("Upload the latest sustainability report PDF. Parses locally — no network calls.")
            pdf_up = st.file_uploader("PDF", type=["pdf"], key=f"pdf_up_{isin_key}")
            if pdf_up is not None and st.button("Parse PDF", key=f"parse_pdf_{isin_key}"):
                with st.spinner("Parsing…"):
                    parsed_seed = parse_emissions(pdf_up.getvalue())
                seed_source = "pdf-upload"

        with ing_tab2:
            st.caption(
                "Paste the direct PDF URL of the latest sustainability report. "
                "Pre-filled from the curated registry where available."
            )
            url_input = st.text_input(
                "Report PDF URL",
                value=stored_url_rec["url"] if stored_url_rec else "",
                key=f"url_in_{isin_key}",
            )
            if url_input and st.button("Fetch + parse", key=f"fetch_url_{isin_key}"):
                with st.spinner(f"Fetching {url_input}…"):
                    try:
                        parsed_seed = fetch_and_parse(url_input)
                        seed_source = "url-paste"
                        seed_url = url_input
                    except Exception as exc:
                        st.error(f"Fetch failed: {exc}")

        with ing_tab3:
            st.caption(
                "Search the web for the company's latest sustainability report PDF. "
                "Best-effort — corporate sites sometimes block automated access. "
                "If this fails, use Upload PDF or Paste URL."
            )
            year_hint = st.number_input("Year hint (optional)", min_value=2018, max_value=2030,
                                         value=2024, step=1, key=f"yh_{isin_key}")
            if st.button("Search", key=f"search_{isin_key}"):
                with st.spinner("Searching…"):
                    try:
                        urls = search_report_url(company, int(year_hint))
                    except Exception as exc:
                        urls = []
                        st.error(f"Search failed: {exc}")
                if urls:
                    st.success(f"Found {len(urls)} candidate URLs.")
                    chosen = st.radio("Pick one to fetch", urls, key=f"pick_{isin_key}")
                    if st.button("Fetch + parse selected", key=f"fp_{isin_key}"):
                        with st.spinner(f"Fetching {chosen}…"):
                            try:
                                parsed_seed = fetch_and_parse(chosen)
                                seed_source = "auto-search"
                                seed_url = chosen
                            except Exception as exc:
                                st.error(f"Fetch failed: {exc}")
                elif urls is not None:
                    st.warning("No PDF candidates found. Try a different year hint or use Paste URL.")

        if parsed_seed and "error" not in parsed_seed:
            resolved = parsed_seed.get("source_url", "")
            original = parsed_seed.get("original_url", "")
            if original and resolved and resolved != original:
                st.info(f"Discovered PDF from landing page: [{resolved}]({resolved})")
            st.success(
                f"Parsed {parsed_seed.get('pages_read', 0)} pages. "
                f"Detected: year={parsed_seed.get('reporting_year')}, "
                f"S1={parsed_seed.get('s1')}, S2={parsed_seed.get('s2')}, S3={parsed_seed.get('s3')}. "
                f"Review and save below."
            )
            if parsed_seed.get("snippets"):
                with st.expander("Show source snippets"):
                    for k, snip in parsed_seed["snippets"].items():
                        st.code(f"{k}: {snip}", language=None)
            if parsed_seed.get("all_candidates"):
                with st.expander(f"Other PDFs found on landing page ({len(parsed_seed['all_candidates'])-1})"):
                    for cand in parsed_seed["all_candidates"][1:]:
                        st.write(
                            f"• [{cand['anchor_text'] or cand['url']}]({cand['url']}) "
                            f"(score: {cand['score']})"
                        )

        # Manual entry form (always available, optionally pre-filled by parser)
        with st.expander("➕ Add or update reported emissions", expanded=parsed_seed is not None):
            seeded_year = (parsed_seed or {}).get("reporting_year") or 2024
            seeded_s1 = float((parsed_seed or {}).get("s1") or 0)
            seeded_s2 = float((parsed_seed or {}).get("s2") or 0)
            seeded_s3 = float((parsed_seed or {}).get("s3") or 0)
            seeded_url = seed_url or ((parsed_seed or {}).get("source_url") or "")
            with st.form(f"emissions_form_{isin_key}"):
                colA, colB, colC = st.columns(3)
                rep_year = colA.number_input("Reporting year", min_value=2000, max_value=2035,
                                             value=int(seeded_year), step=1)
                s1 = colB.number_input("Scope 1 (tCO2e)", min_value=0.0, value=seeded_s1, step=1000.0, format="%.0f")
                s2 = colC.number_input("Scope 2 (tCO2e)", min_value=0.0, value=seeded_s2, step=1000.0, format="%.0f")
                colD, colE, colF = st.columns(3)
                s3 = colD.number_input("Scope 3 (tCO2e, optional)", min_value=0.0, value=seeded_s3, step=1000.0, format="%.0f")
                base_year_in = colE.number_input("Base year", min_value=2000, max_value=2030, value=2019, step=1)
                base_s12_in = colF.number_input("Base year S1+S2 (tCO2e)", min_value=0.0, value=0.0, step=1000.0, format="%.0f")
                source_url = st.text_input("Source URL (sustainability report link)", value=seeded_url)
                source_kind = st.selectbox(
                    "Data source", ["manual", "pdf-upload", "url-paste", "auto-search"],
                    index={"manual": 0, "pdf-upload": 1, "url-paste": 2, "auto-search": 3}.get(seed_source or "manual", 0),
                )
                submitted = st.form_submit_button("Save")
                if submitted:
                    upsert_record(
                        emissions_cache, company=company, isin=isin_key or None,
                        reporting_year=int(rep_year),
                        s1=s1 or None, s2=s2 or None, s3=s3 or None,
                        base_year=int(base_year_in) if base_year_in else None,
                        base_s12=base_s12_in or None,
                        source=source_kind,
                        source_url=source_url,
                    )
                    save_cache(emissions_cache)
                    st.success(f"Saved {company} {int(rep_year)} emissions. Reload to refresh the cohort table.")


with tab_rulebook:
    st.markdown("### Sector adequacy rulebook")
    st.caption(
        "These are the required scopes per SBTi published sector guidance. "
        "First matching rule wins. Edit `modules/sbti_phase1.py` to refine."
    )
    rb = pd.DataFrame([
        {
            "Applicable SBTi guidance": r.name,
            "Required scopes": ", ".join(r.required),
            "Sector keywords matched": ", ".join(r.applies_to),
            "Note": r.note,
        }
        for r in SECTOR_RULES
    ])
    st.dataframe(rb, use_container_width=True, hide_index=True, height=520)


st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ Methodology"):
    st.markdown(
        "**Outreach priority** = high if target year ≤2030, target year already "
        "passed, or required Scope 3 categories are missing per applicable SBTi "
        "sector guidance.\n\n"
        "**Target year source:** prefers near-term, falls back to long-term, then "
        "net-zero year.\n\n"
        "**TPI MQ/CP** (Management Quality / Carbon Performance) levels are "
        "synthesised from SBTi disclosure data using TPI's framework structure — "
        "they are directional indicators, not authoritative TPI assessments.\n\n"
        "**Delivery RAG** compares actual reduction (latest reporting year) "
        "against the linear-path required reduction implied by each company's "
        "own committed target."
    )
