"""Phase 1 — ASX SBTi target screen.

Run: streamlit run sbti_tracker.py
"""

from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.sbti import CANON, DATA_DIR, load_sbti
from modules.sbti_phase1 import (
    DISPLAY_COLS,
    SECTOR_RULES,
    V2_COLOUR,
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

st.set_page_config(
    page_title="ASX SBTi Target Screen — Phase 1",
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
st.sidebar.title("🇦🇺 ASX SBTi Screen")
st.sidebar.caption("Phase 1 — target adequacy & V2 reset risk")

st.sidebar.markdown("### Data source")
sbti_upload = st.sidebar.file_uploader(
    "SBTi Companies-Taking-Action (CSV/XLSX)",
    type=["csv", "xlsx", "xls"],
    help="Download from sciencebasedtargets.org/companies-taking-action",
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
    st.title("🇦🇺 ASX SBTi Target Screen — Phase 1")
    st.warning(
        f"No SBTi data loaded. Upload the **Companies Taking Action** dataset in the "
        f"sidebar, or commit it to `{DATA_DIR / 'sbti_companies.xlsx'}` and reload.\n\n"
        "Source: https://sciencebasedtargets.org/companies-taking-action"
    )
    st.stop()

screen = build_screen(sbti_df)

# ─── Phase 2 emissions data ingestion ────────────────────────────────────────
emissions_cache = load_cache()

st.sidebar.markdown("### Phase 2 — emissions data")
emissions_csv = st.sidebar.file_uploader(
    "Bulk upload emissions CSV",
    type=["csv"],
    help="Use the template (download below) for batch ingest of reported emissions.",
)
if emissions_csv is not None:
    try:
        n = merge_csv(emissions_cache, emissions_csv.getvalue())
        save_cache(emissions_cache)
        st.sidebar.success(f"Merged {n} rows into emissions cache.")
    except Exception as exc:
        st.sidebar.error(f"CSV merge failed: {exc}")

st.sidebar.download_button(
    "📥 Download emissions CSV template",
    csv_template_bytes(),
    file_name="emissions_template.csv",
    mime="text/csv",
)

# Apply Phase 2 deliverability scoring on top of Phase 1.
screen = build_delivery(screen, emissions_cache)


# ─── Sidebar: filters ──────────────────────────────────────────────────────────
st.sidebar.markdown("### Filters")
sectors = sorted([s for s in screen[CANON["sector"]].dropna().unique() if str(s).strip()])

f_sector = st.sidebar.multiselect("Sector", sectors)
f_v2 = st.sidebar.radio("V2 reset likely", ["All", "Yes", "No"], index=0)
f_yrs = st.sidebar.slider(
    "Years to target (range)",
    min_value=-10, max_value=30, value=(-10, 15), step=1,
    help="Negative = target year already passed. Default surfaces companies with targets due ≤15 yrs out.",
)
search = st.sidebar.text_input("Search company")

filtered = screen.copy()
if f_sector:
    filtered = filtered[filtered[CANON["sector"]].isin(f_sector)]
if f_v2 != "All":
    filtered = filtered[filtered["V2 Reset Likely"] == f_v2]
yrs_lo, yrs_hi = f_yrs
mask = filtered["Years to Target"].between(yrs_lo, yrs_hi, inclusive="both")
mask = mask | filtered["Years to Target"].isna()
filtered = filtered[mask]
if search:
    filtered = filtered[filtered[CANON["company"]].str.contains(search, case=False, na=False)]


# ─── Main: header + KPIs ───────────────────────────────────────────────────────
st.title("🇦🇺 ASX SBTi Target Screen — Phase 1")
st.caption(
    "ASX-listed cohort (Australia + AU ISIN) from the SBTi public dataset. "
    "Targets validated by SBTi are presumed scope-adequate at validation time, so "
    "we don't surface a separate scope-adequacy RAG. The V2 reset flag captures "
    "targets that will need to change: target year ≤2030 (V2 near-term horizon), "
    "target year already passed, or required scopes missing per applicable SBTi sector guidance."
)

total = len(filtered)
target_set = filtered[CANON["near_term_status"]].astype(str).str.lower().str.contains("targets set", na=False).sum()
due_2030 = int((filtered["Target Year (used)"] <= 2030).fillna(False).sum())
expired = int((filtered["Years to Target"] < 0).fillna(False).sum())
v2_yes = int((filtered["V2 Reset Likely"] == "Yes").sum())
no_year = int(filtered["Years to Target"].isna().sum())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("ASX SBTi cohort", f"{total:,}")
c2.metric("⏰ Target ≤2030", f"{due_2030:,}")
c3.metric("⏳ Target year passed", f"{expired:,}")
c4.metric("⚠️ V2 reset likely", f"{v2_yes:,}")
c5.metric("ℹ️ No target year", f"{no_year:,}")


tab_screen, tab_delivery, tab_charts, tab_company, tab_rulebook = st.tabs(
    ["Phase 1 + 2 screen", "Phase 2 — Delivery", "Sector heatmap", "Company drill-down", "Sector rulebook"]
)


with tab_screen:
    st.markdown("### Phase 1 cohort — ranked by target proximity")
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
    st.dataframe(styler, use_container_width=True, height=620, hide_index=True)

    st.download_button(
        "Download Phase 1 screen (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="asx_sbti_phase1_screen.csv",
        mime="text/csv",
    )

    bd1, bd2 = st.columns(2)
    with bd1:
        st.markdown("**BD play 1 — Looming targets (≤2030)**")
        bd1_df = (
            filtered[filtered["Target Year (used)"] <= 2030]
            [[CANON["company"], CANON["sector"], "Target Year (used)", "Years to Target",
              "Applicable SBTi Guidance"]]
            .sort_values("Years to Target")
        )
        st.dataframe(bd1_df, use_container_width=True, height=280, hide_index=True)
    with bd2:
        st.markdown("**BD play 2 — V2 will force a reset**")
        bd2_df = (
            filtered[filtered["V2 Reset Likely"] == "Yes"]
            [[CANON["company"], CANON["sector"], "V2 Reset Reasons"]]
        )
        st.dataframe(bd2_df, use_container_width=True, height=280, hide_index=True)


with tab_delivery:
    st.markdown("### Phase 2 — Delivery against committed trajectory")
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
                 use_container_width=True, height=520, hide_index=True)
    st.download_button(
        "Download delivery table (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="asx_sbti_phase2_delivery.csv",
        mime="text/csv",
    )

    st.markdown(
        "**To populate emissions data:** either (a) bulk-upload the CSV template "
        "from the sidebar, or (b) enter per-company in the **Company drill-down** tab. "
        "All entries persist to `data/emissions_cache.json` — committing that file "
        "to the repo makes the data permanent for the team."
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
        col2.metric("Target year (used)",
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

        # ── Phase 2: emissions trajectory + manual entry ──
        st.markdown("---")
        st.markdown("### Phase 2 — Delivery against committed trajectory")

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

        # Manual entry form
        with st.expander("➕ Add or update reported emissions"):
            with st.form(f"emissions_form_{isin_key}"):
                colA, colB, colC = st.columns(3)
                rep_year = colA.number_input("Reporting year", min_value=2000, max_value=2035, value=2024, step=1)
                s1 = colB.number_input("Scope 1 (tCO2e)", min_value=0.0, value=0.0, step=1000.0, format="%.0f")
                s2 = colC.number_input("Scope 2 (tCO2e)", min_value=0.0, value=0.0, step=1000.0, format="%.0f")
                colD, colE, colF = st.columns(3)
                s3 = colD.number_input("Scope 3 (tCO2e, optional)", min_value=0.0, value=0.0, step=1000.0, format="%.0f")
                base_year_in = colE.number_input("Base year", min_value=2000, max_value=2030, value=2019, step=1)
                base_s12_in = colF.number_input("Base year S1+S2 (tCO2e)", min_value=0.0, value=0.0, step=1000.0, format="%.0f")
                source_url = st.text_input("Source URL (sustainability report link)", value="")
                submitted = st.form_submit_button("Save")
                if submitted:
                    upsert_record(
                        emissions_cache, company=company, isin=isin_key or None,
                        reporting_year=int(rep_year),
                        s1=s1 or None, s2=s2 or None, s3=s3 or None,
                        base_year=int(base_year_in) if base_year_in else None,
                        base_s12=base_s12_in or None,
                        source="manual",
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
st.sidebar.caption(
    "**V2 reset triggers:** target year ≤2030 (V2 near-term horizon) OR target year "
    "already passed OR required scopes missing per applicable SBTi sector guidance.\n\n"
    "**Target year source:** prefers near-term, falls back to long-term, then net-zero."
)
