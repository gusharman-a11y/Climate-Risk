"""SBTi Company Tracker — Streamlit app.

Run with:
    streamlit run sbti_tracker.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.sbti import (
    ASEAN_AU_NZ_JP,
    CANON,
    DATA_DIR,
    RAG_COLOUR,
    attach_cdp,
    attach_size_data,
    load_sbti,
    parse_report,
    score,
)

st.set_page_config(
    page_title="SBTi Company Tracker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
[data-testid="stSidebar"] { background-color: #0F172A; }
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
.metric-card { background: #F8FAFC; border-left: 4px solid #3B82F6; padding: 0.75rem 1rem; border-radius: 4px; }
.rag-Green  { color: #16A34A; font-weight: 700; }
.rag-Amber  { color: #D97706; font-weight: 700; }
.rag-Red    { color: #DC2626; font-weight: 700; }
.rag-OffTrack { color: #7F1D1D; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Sidebar: data sources ─────────────────────────────────────────────────────
st.sidebar.title("🎯 SBTi Tracker")
st.sidebar.caption("Composite RAG view of SBTi company progress")

st.sidebar.markdown("### Data sources")
sbti_upload = st.sidebar.file_uploader(
    "SBTi Companies-Taking-Action (CSV/XLSX)",
    type=["csv", "xlsx", "xls"],
    help="Download from sciencebasedtargets.org/companies-taking-action",
)
size_upload = st.sidebar.file_uploader(
    "Optional: company size (Revenue/Assets/Employees)",
    type=["csv", "xlsx"],
    help="Used to apply ASRS Group 1/2 tiering. Columns: Company Name, Revenue (AUD), Assets (AUD), Employees",
)
cdp_upload = st.sidebar.file_uploader(
    "Optional: public CDP scores",
    type=["csv", "xlsx"],
    help="Columns: Company Name, CDP Score",
)


@st.cache_data(show_spinner=False)
def _load(file_bytes: bytes | None, name: str | None):
    if file_bytes is None:
        return load_sbti(None)
    buf = io.BytesIO(file_bytes)
    buf.name = name or "upload.csv"
    return load_sbti(buf)


def _to_buf(upload):
    if upload is None:
        return None
    b = io.BytesIO(upload.getvalue())
    b.name = upload.name
    return b


sbti_df = _load(sbti_upload.getvalue() if sbti_upload else None,
                sbti_upload.name if sbti_upload else None)

if sbti_df.empty:
    st.title("🎯 SBTi Company Tracker")
    st.warning(
        "No SBTi data loaded. Upload the **Companies Taking Action** dataset in the sidebar, "
        f"or drop the file at `{DATA_DIR / 'sbti_companies.csv'}` and reload.\n\n"
        "Source: https://sciencebasedtargets.org/companies-taking-action"
    )
    st.markdown(
        "**Expected columns** (any subset works — common SBTi headers are auto-detected): "
        "`Company Name`, `ISIN`, `Country`, `Sector`, `Organization Type`, `Action`, "
        "`Target`, `Target Classification`, `Target Year`, `Base Year`, `Status`, "
        "`Near-term - Target Status`, `Net-Zero Year`, `Ambition`, `Date Committed`, `Date Published`."
    )
    st.stop()


df = attach_size_data(sbti_df, _to_buf(size_upload))
df = attach_cdp(df, _to_buf(cdp_upload))
df = score(df)


# ── Sidebar: filters ──────────────────────────────────────────────────────────
st.sidebar.markdown("### Filters")

countries = sorted([c for c in df[CANON["country"]].dropna().unique() if str(c).strip()])
sectors = sorted([c for c in df[CANON["sector"]].dropna().unique() if str(c).strip()])
tiers = sorted([c for c in df["ASRS Tier"].dropna().unique() if str(c).strip()])

quick = st.sidebar.radio(
    "Quick view",
    ["All companies", "AU + NZ + Japan + ASEAN", "Off-track only", "Tier 1 & 2 deep-dive"],
    index=0,
)

selected_countries = st.sidebar.multiselect("Country", countries, default=[])
selected_sectors = st.sidebar.multiselect("Sector", sectors, default=[])
selected_tiers = st.sidebar.multiselect("ASRS Tier", tiers, default=[])
search = st.sidebar.text_input("Search company")

filtered = df.copy()
if quick == "AU + NZ + Japan + ASEAN":
    filtered = filtered[filtered[CANON["country"]].isin(ASEAN_AU_NZ_JP)]
elif quick == "Off-track only":
    filtered = filtered[filtered["RAG"].isin(["Red", "Off Track"])]
elif quick == "Tier 1 & 2 deep-dive":
    filtered = filtered[filtered[CANON["country"]].isin(ASEAN_AU_NZ_JP)]
    filtered = filtered[filtered["ASRS Tier"].isin(["Group 1", "Group 2", "Group 2 (proxy)"])]

if selected_countries:
    filtered = filtered[filtered[CANON["country"]].isin(selected_countries)]
if selected_sectors:
    filtered = filtered[filtered[CANON["sector"]].isin(selected_sectors)]
if selected_tiers:
    filtered = filtered[filtered["ASRS Tier"].isin(selected_tiers)]
if search:
    filtered = filtered[filtered[CANON["company"]].str.contains(search, case=False, na=False)]


# ── Main view ────────────────────────────────────────────────────────────────
st.title("🎯 SBTi Company Tracker")
st.caption(
    "Composite progress score across SBTi target status, ambition, net-zero commitment, "
    "expiry risk, and disclosure recency."
)

c1, c2, c3, c4, c5 = st.columns(5)
total = len(filtered)
counts = filtered["RAG"].value_counts().to_dict() if total else {}
c1.metric("Companies in view", f"{total:,}")
c2.metric("🟢 Green", f"{counts.get('Green', 0):,}")
c3.metric("🟡 Amber", f"{counts.get('Amber', 0):,}")
c4.metric("🔴 Red", f"{counts.get('Red', 0):,}")
c5.metric("⚫ Off Track", f"{counts.get('Off Track', 0):,}")

if total == 0:
    st.info("No companies match the current filters.")
    st.stop()


tab_overview, tab_offtrack, tab_table, tab_company = st.tabs(
    ["Overview", "Off-track leaderboard", "Table", "Company drill-down"]
)


with tab_overview:
    col_left, col_right = st.columns([3, 2])

    with col_left:
        rag_counts = (
            filtered["RAG"].value_counts()
            .reindex(["Green", "Amber", "Red", "Off Track"]).fillna(0).reset_index()
        )
        rag_counts.columns = ["RAG", "Companies"]
        fig = px.bar(
            rag_counts, x="RAG", y="Companies",
            color="RAG", color_discrete_map=RAG_COLOUR,
            title="RAG distribution",
        )
        fig.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig, use_container_width=True)

        sector_rag = (
            filtered.groupby([CANON["sector"], "RAG"]).size().reset_index(name="Companies")
        )
        if not sector_rag.empty:
            fig2 = px.bar(
                sector_rag, x=CANON["sector"], y="Companies", color="RAG",
                color_discrete_map=RAG_COLOUR, title="RAG by sector",
            )
            fig2.update_layout(height=420, xaxis={"categoryorder": "total descending"})
            st.plotly_chart(fig2, use_container_width=True)

    with col_right:
        country_rag = (
            filtered.groupby([CANON["country"], "RAG"]).size().reset_index(name="Companies")
        )
        if not country_rag.empty:
            top_countries = (
                country_rag.groupby(CANON["country"])["Companies"].sum()
                .nlargest(15).index.tolist()
            )
            country_rag = country_rag[country_rag[CANON["country"]].isin(top_countries)]
            fig3 = px.bar(
                country_rag, y=CANON["country"], x="Companies", color="RAG", orientation="h",
                color_discrete_map=RAG_COLOUR, title="Top 15 countries — RAG mix",
            )
            fig3.update_layout(height=820, yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig3, use_container_width=True)


with tab_offtrack:
    st.markdown("### Companies most likely to miss their targets")
    st.caption(
        "Sorted by composite score, lowest first. Red = at risk; Off Track = removed/expired/no progress."
    )
    off = filtered[filtered["RAG"].isin(["Red", "Off Track"])].copy()
    off = off.sort_values("Composite Score", ascending=True)

    show_cols = [
        CANON["company"], CANON["country"], CANON["sector"], "ASRS Tier",
        CANON["near_term_status"], CANON["long_term_status"], CANON["net_zero_status"],
        CANON["target_year"], CANON["net_zero_year"], CANON["target_class_long"],
        CANON["removal_reason"], "Composite Score", "RAG",
    ]
    show_cols = [c for c in show_cols if c in off.columns]
    st.dataframe(off[show_cols], use_container_width=True, height=600, hide_index=True)

    st.download_button(
        "Download off-track list (CSV)",
        off[show_cols].to_csv(index=False).encode("utf-8"),
        file_name="sbti_off_track.csv",
        mime="text/csv",
    )


with tab_table:
    st.markdown("### Full filtered dataset")
    sort_col = st.selectbox("Sort by", ["Composite Score", CANON["company"], CANON["country"]])
    ascending = st.checkbox("Ascending", value=(sort_col == "Composite Score"))
    table = filtered.sort_values(sort_col, ascending=ascending)
    st.dataframe(table, use_container_width=True, height=600, hide_index=True)
    st.download_button(
        "Download filtered (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="sbti_filtered.csv",
        mime="text/csv",
    )


with tab_company:
    st.markdown("### Company drill-down")
    company = st.selectbox(
        "Select company",
        sorted(filtered[CANON["company"]].dropna().unique()),
    )
    rec = filtered[filtered[CANON["company"]] == company].iloc[0]

    badge = rec["RAG"].replace(" ", "")
    st.markdown(
        f"#### {company} &nbsp; <span class='rag-{badge}'>● {rec['RAG']}</span>",
        unsafe_allow_html=True,
    )

    a, b, c, d = st.columns(4)
    a.metric("Country", str(rec.get(CANON["country"], "—")))
    b.metric("Sector", str(rec.get(CANON["sector"], "—")))
    c.metric("ASRS Tier", str(rec.get("ASRS Tier", "—")))
    d.metric("Composite", int(rec["Composite Score"]))

    st.markdown("**Targets**")
    target_cols = {
        "Near-term status": rec.get(CANON["near_term_status"]),
        "Long-term status": rec.get(CANON["long_term_status"]),
        "Net-Zero status": rec.get(CANON["net_zero_status"]),
        "Classification (short)": rec.get(CANON["target_class"]),
        "Classification (long)": rec.get(CANON["target_class_long"]),
        "Ambition": rec.get(CANON["ambition"]),
        "Base year": rec.get(CANON["base_year"]),
        "Near-term target year": rec.get(CANON["target_year"]),
        "Long-term target year": rec.get(CANON["long_term_target_year"]),
        "Net-Zero year": rec.get(CANON["net_zero_year"]),
        "BA1.5 status": rec.get(CANON["ba15_status"]),
        "BA1.5 date": rec.get(CANON["ba15_date"]),
        "Date committed": rec.get(CANON["date_committed"]),
        "Date updated": rec.get(CANON["date_updated"]),
        "Removal/Extension reason": rec.get(CANON["removal_reason"]),
    }
    st.table(pd.DataFrame(target_cols.items(), columns=["Field", "Value"]))

    if pd.notna(rec.get(CANON["target"])):
        st.markdown("**Target wording**")
        st.info(str(rec[CANON["target"]]))

    st.markdown("**Score breakdown**")
    breakdown = pd.DataFrame({
        "Component": ["Status", "Ambition", "Net-Zero", "Expired", "Recency"],
        "Points": [rec["Status pts"], rec["Ambition pts"], rec["Net-Zero pts"],
                   rec["Expired pts"], rec["Recency pts"]],
    })
    fig_bd = go.Figure(go.Bar(
        x=breakdown["Component"], y=breakdown["Points"],
        marker_color=["#16A34A" if v >= 0 else "#DC2626" for v in breakdown["Points"]],
    ))
    fig_bd.update_layout(height=280, yaxis_title="Points",
                         title=f"Composite = {int(rec['Composite Score'])}")
    st.plotly_chart(fig_bd, use_container_width=True)

    st.markdown("---")
    st.markdown("### Sustainability report ingestion")
    st.caption("Upload the company's latest sustainability report (PDF) to extract reported Scope 1/2/3 emissions and target mentions.")
    pdf = st.file_uploader("Sustainability report PDF", type=["pdf"], key=f"pdf_{company}")
    if pdf is not None:
        with st.spinner("Parsing report…"):
            result = parse_report(pdf.getvalue())
        if "error" in result:
            st.error(result["error"])
        else:
            st.success(f"Parsed {result['pages_read']} pages.")
            sf = result["scope_findings"]
            cols = st.columns(3)
            for col, scope in zip(cols, ["Scope 1", "Scope 2", "Scope 3"]):
                with col:
                    st.markdown(f"**{scope}**")
                    if sf[scope]:
                        for v in sf[scope][:8]:
                            st.write(f"• {v}")
                    else:
                        st.caption("No matches")
            if result["target_mentions"]:
                st.markdown("**Target / net-zero mentions**")
                for m in result["target_mentions"][:10]:
                    st.write(f"• {m}")


st.sidebar.markdown("---")
st.sidebar.caption(
    "Composite scoring: Status (−2..3) + Ambition (0..3) + Net-Zero (0..1) "
    "+ Expired penalty (−2..0) + Recency (0..2). "
    "Bands: Green ≥ 7, Amber ≥ 4, Red ≥ 1, Off Track < 1."
)
