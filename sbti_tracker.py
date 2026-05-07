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
    ADEQUACY_COLOUR,
    DISPLAY_COLS,
    SECTOR_RULES,
    applicable_rule,
    build_screen,
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
.adq-Green { color: #16A34A; font-weight: 700; }
.adq-Amber { color: #D97706; font-weight: 700; }
.adq-Red   { color: #DC2626; font-weight: 700; }
.adq-NA    { color: #6B7280; font-weight: 600; }
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


# ─── Sidebar: filters ──────────────────────────────────────────────────────────
st.sidebar.markdown("### Filters")
sectors = sorted([s for s in screen[CANON["sector"]].dropna().unique() if str(s).strip()])
adequacies = ["Red", "Amber", "Green", "N/A"]

f_sector = st.sidebar.multiselect("Sector", sectors)
f_adequacy = st.sidebar.multiselect("Scope adequacy", adequacies)
f_v2 = st.sidebar.radio("V2 reset likely", ["All", "Yes", "No"], index=0)
f_yrs = st.sidebar.slider(
    "Years to target (range)",
    min_value=-5, max_value=30, value=(-5, 15), step=1,
    help="Negative = target year already passed. Default surfaces companies with targets due ≤15 yrs out.",
)
search = st.sidebar.text_input("Search company")

filtered = screen.copy()
if f_sector:
    filtered = filtered[filtered[CANON["sector"]].isin(f_sector)]
if f_adequacy:
    filtered = filtered[filtered["Scope Adequacy"].isin(f_adequacy)]
if f_v2 != "All":
    filtered = filtered[filtered["V2 Reset Likely"] == f_v2]
yrs_lo, yrs_hi = f_yrs
mask = filtered["Years to Target"].between(yrs_lo, yrs_hi, inclusive="both")
mask = mask | filtered["Years to Target"].isna()  # keep rows with no target year unless filter is strict
filtered = filtered[mask]
if search:
    filtered = filtered[filtered[CANON["company"]].str.contains(search, case=False, na=False)]


# ─── Main: header + KPIs ───────────────────────────────────────────────────────
st.title("🇦🇺 ASX SBTi Target Screen — Phase 1")
st.caption(
    "ASX-listed cohort (Australia + AU ISIN) from the SBTi public dataset. "
    "Adequacy assessed against published SBTi sector guidance. "
    "V2 reset flag = target imminent OR required scopes missing OR sector guidance applies but not followed."
)

total = len(filtered)
imminent = int((filtered["Years to Target"] <= 2).fillna(False).sum())
red = int((filtered["Scope Adequacy"] == "Red").sum())
amber = int((filtered["Scope Adequacy"] == "Amber").sum())
green = int((filtered["Scope Adequacy"] == "Green").sum())
v2_yes = int((filtered["V2 Reset Likely"] == "Yes").sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("ASX SBTi cohort", f"{total:,}")
c2.metric("⏰ Targets due ≤2 yrs", f"{imminent:,}")
c3.metric("🔴 Scope Red", f"{red:,}")
c4.metric("🟡 Scope Amber", f"{amber:,}")
c5.metric("🟢 Scope Green", f"{green:,}")
c6.metric("⚠️ V2 reset likely", f"{v2_yes:,}")


tab_screen, tab_charts, tab_company, tab_rulebook = st.tabs(
    ["Phase 1 screen", "Sector heatmap", "Company drill-down", "Sector rulebook"]
)


with tab_screen:
    st.markdown("### Phase 1 cohort — ranked by target proximity")
    st.caption("Sorted by **Years to Target** ascending — most imminent first.")

    cols_present = [c for c in DISPLAY_COLS if c in filtered.columns]
    table = filtered[cols_present].copy()

    def _row_style(row):
        colour = ADEQUACY_COLOUR.get(row["Scope Adequacy"], "#FFFFFF")
        # Only tint the adequacy cell
        return [
            f"background-color: {colour}22; color: {colour}; font-weight: 600"
            if c == "Scope Adequacy" else "" for c in row.index
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
        st.markdown("**BD play 1 — Looming targets**")
        bd1_df = (
            filtered[filtered["Years to Target"] <= 3]
            [[CANON["company"], CANON["sector"], "Years to Target", "Scope Adequacy"]]
            .sort_values("Years to Target")
        )
        st.dataframe(bd1_df, use_container_width=True, height=280, hide_index=True)
    with bd2:
        st.markdown("**BD play 2 — Scope holes (V2 will force a fix)**")
        bd2_df = (
            filtered[(filtered["Scope Adequacy"] == "Red") & (filtered["V2 Reset Likely"] == "Yes")]
            [[CANON["company"], CANON["sector"], "Scope Gap", "V2 Reset Reasons"]]
        )
        st.dataframe(bd2_df, use_container_width=True, height=280, hide_index=True)


with tab_charts:
    st.markdown("### Adequacy distribution by SBTi sector guidance")
    rule_dist = (
        filtered.groupby(["Applicable SBTi Guidance", "Scope Adequacy"])
        .size().reset_index(name="Companies")
    )
    if not rule_dist.empty:
        fig = px.bar(
            rule_dist, x="Applicable SBTi Guidance", y="Companies", color="Scope Adequacy",
            color_discrete_map=ADEQUACY_COLOUR, barmode="stack",
        )
        fig.update_layout(height=480, xaxis_tickangle=-30,
                          xaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Target-year profile")
    yr_df = filtered[filtered[CANON["target_year"]].notna()].copy()
    if not yr_df.empty:
        yr_df["Year"] = yr_df[CANON["target_year"]].astype(int)
        year_dist = (
            yr_df.groupby(["Year", "Scope Adequacy"]).size().reset_index(name="Companies")
        )
        fig2 = px.bar(
            year_dist, x="Year", y="Companies", color="Scope Adequacy",
            color_discrete_map=ADEQUACY_COLOUR, barmode="stack",
        )
        fig2.update_layout(height=380, xaxis_dtick=1)
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

        adq = rec["Scope Adequacy"]
        adq_class = adq.replace("/", "").replace(" ", "")
        st.markdown(
            f"#### {company} &nbsp; <span class='adq-{adq_class}'>● Scope {adq}</span> "
            f"&nbsp; V2 reset: **{rec['V2 Reset Likely']}**",
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Sector", str(rec.get(CANON["sector"], "—")))
        col2.metric("Near-term target year", str(rec.get(CANON["target_year"], "—")))
        col3.metric(
            "Years to target",
            "—" if pd.isna(rec["Years to Target"]) else int(rec["Years to Target"]),
        )
        col4.metric("Net-Zero year", str(rec.get(CANON["net_zero_year"], "—")))

        st.markdown(f"**Applicable SBTi guidance:** {rec['Applicable SBTi Guidance']}")
        st.markdown(f"**Required scopes:** {rec['Required Scopes']}")
        st.markdown(f"**Target scopes covered:** {rec['Target Scopes Covered']}")
        st.markdown(f"**Scope gap:** {rec['Scope Gap']}")

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
    "**Adequacy bands:** Green = all required scopes covered. Amber = 1 missing. "
    "Red = 2+ missing. N/A = no SBTi sector guidance applies.\n\n"
    "**V2 reset triggers:** target due in ≤2 yrs OR required scopes missing OR "
    "SBTi sector guidance applies but target doesn't follow it."
)
