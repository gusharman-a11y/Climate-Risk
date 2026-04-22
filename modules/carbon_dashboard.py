"""
Carbon Market Dashboard – Streamlit page renderer.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from modules.carbon_data import get_projects_df, get_issuances_df, unique_values

# ── Colour palette ─────────────────────────────────────────────────────────────
STATUS_COLOURS = {
    "Active":           {"bg": "#DCFCE7", "text": "#15803D"},
    "Retired":          {"bg": "#F1F5F9", "text": "#475569"},
    "Under Validation": {"bg": "#FEF3C7", "text": "#D97706"},
    "Suspended":        {"bg": "#FEE2E2", "text": "#DC2626"},
}

TYPE_COLOURS = {
    "REDD+":            "#1D4ED8",
    "ARR":              "#15803D",
    "IFM":              "#065F46",
    "Blue Carbon":      "#0369A1",
    "Clean Cooking":    "#B45309",
    "Renewable Energy": "#7C3AED",
    "Soil Carbon":      "#92400E",
    "Fire Management":  "#C2410C",
    "Methane Avoidance":"#475569",
}

STANDARD_COLOURS = {
    "Verra VCS":   "#1D4ED8",
    "Gold Standard":"#D97706",
    "ACR":         "#15803D",
    "CAR":         "#7C3AED",
    "ACCU":        "#0369A1",
}


def _fmt_credits(n: float) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f} M"
    if n >= 1_000:
        return f"{n/1_000:.0f} K"
    return str(int(n))


def _status_badge(status: str) -> str:
    cfg = STATUS_COLOURS.get(status, {"bg": "#F3F4F6", "text": "#6B7280"})
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'font-size:0.75rem;font-weight:600;background:{cfg["bg"]};color:{cfg["text"]}">'
        f"{status}</span>"
    )


# ── Main entry point ───────────────────────────────────────────────────────────

def render_carbon_dashboard() -> None:
    st.title("Carbon Market Dashboard")
    st.markdown(
        "An overview of carbon market projects and credit issuances across "
        "voluntary and compliance markets."
    )

    projects_df = get_projects_df()
    issuances_df = get_issuances_df()

    # ── Sidebar filters ────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("---")
        st.markdown("**Dashboard Filters**")

        sel_types = st.multiselect(
            "Project type",
            options=unique_values("type"),
            default=[],
            placeholder="All types",
        )
        sel_countries = st.multiselect(
            "Country",
            options=unique_values("country"),
            default=[],
            placeholder="All countries",
        )
        sel_standards = st.multiselect(
            "Standard",
            options=unique_values("standard"),
            default=[],
            placeholder="All standards",
        )
        sel_statuses = st.multiselect(
            "Status",
            options=unique_values("status"),
            default=[],
            placeholder="All statuses",
        )
        vintage_years = sorted(issuances_df["vintage_year"].unique())
        year_range = st.slider(
            "Vintage year range",
            min_value=int(vintage_years[0]),
            max_value=int(vintage_years[-1]),
            value=(int(vintage_years[0]), int(vintage_years[-1])),
        )

    # ── Apply filters ──────────────────────────────────────────────────────────
    pf = projects_df.copy()
    if sel_types:
        pf = pf[pf["type"].isin(sel_types)]
    if sel_countries:
        pf = pf[pf["country"].isin(sel_countries)]
    if sel_standards:
        pf = pf[pf["standard"].isin(sel_standards)]
    if sel_statuses:
        pf = pf[pf["status"].isin(sel_statuses)]

    filtered_ids = set(pf["id"])
    isf = issuances_df[
        issuances_df["project_id"].isin(filtered_ids)
        & issuances_df["vintage_year"].between(year_range[0], year_range[1])
    ]

    # ── KPI row ────────────────────────────────────────────────────────────────
    total_issued = isf["credits_issued"].sum()
    total_retired = isf["credits_retired"].sum()
    outstanding = total_issued - total_retired
    active_count = len(pf[pf["status"] == "Active"])

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Projects", len(pf))
    k2.metric("Active Projects", active_count)
    k3.metric("Credits Issued", _fmt_credits(total_issued) + " tCO₂e")
    k4.metric("Credits Retired", _fmt_credits(total_retired) + " tCO₂e")
    k5.metric("Outstanding", _fmt_credits(outstanding) + " tCO₂e")

    st.markdown("---")

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab_overview, tab_projects, tab_issuances = st.tabs(
        ["Overview", "Projects", "Issuances"]
    )

    with tab_overview:
        _render_overview(pf, isf)

    with tab_projects:
        _render_projects(pf)

    with tab_issuances:
        _render_issuances(isf)


# ── Overview tab ───────────────────────────────────────────────────────────────

def _render_overview(pf: pd.DataFrame, isf: pd.DataFrame) -> None:
    # Annual issuance trend
    st.markdown("### Annual Credit Issuances vs Retirements")
    if isf.empty:
        st.info("No issuance data for current filters.")
    else:
        yearly = (
            isf.groupby("vintage_year")
            .agg(issued=("credits_issued", "sum"), retired=("credits_retired", "sum"))
            .reset_index()
        )
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=yearly["vintage_year"], y=yearly["issued"],
            name="Issued", marker_color="#3B82F6",
            hovertemplate="Vintage %{x}<br>Issued: %{y:,.0f} tCO₂e<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=yearly["vintage_year"], y=yearly["retired"],
            name="Retired", marker_color="#10B981",
            hovertemplate="Vintage %{x}<br>Retired: %{y:,.0f} tCO₂e<extra></extra>",
        ))
        fig.update_layout(
            barmode="group",
            xaxis=dict(title="Vintage Year", tickmode="linear", dtick=1),
            yaxis=dict(title="tCO₂e", tickformat=",.0f", gridcolor="#F1F5F9"),
            plot_bgcolor="white", paper_bgcolor="white",
            height=340, margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=1.08),
            font=dict(family="Inter, Helvetica, sans-serif", size=12),
        )
        st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### Credits Issued by Project Type")
        if not isf.empty:
            by_type = (
                isf.groupby("type")["credits_issued"].sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            colours = [TYPE_COLOURS.get(t, "#94A3B8") for t in by_type["type"]]
            fig2 = go.Figure(go.Bar(
                x=by_type["credits_issued"],
                y=by_type["type"],
                orientation="h",
                marker_color=colours,
                hovertemplate="%{y}<br>%{x:,.0f} tCO₂e<extra></extra>",
                text=[_fmt_credits(v) for v in by_type["credits_issued"]],
                textposition="outside",
            ))
            fig2.update_layout(
                xaxis=dict(tickformat=",.0f", gridcolor="#F1F5F9"),
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="white", paper_bgcolor="white",
                height=320, margin=dict(l=10, r=60, t=10, b=10),
                font=dict(family="Inter, Helvetica, sans-serif", size=12),
            )
            st.plotly_chart(fig2, use_container_width=True)

    with col_right:
        st.markdown("### Credits Issued by Standard")
        if not isf.empty:
            by_std = (
                isf.groupby("standard")["credits_issued"].sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            std_colours = [STANDARD_COLOURS.get(s, "#94A3B8") for s in by_std["standard"]]
            fig3 = go.Figure(go.Pie(
                labels=by_std["standard"],
                values=by_std["credits_issued"],
                marker_colors=std_colours,
                hole=0.45,
                hovertemplate="%{label}<br>%{value:,.0f} tCO₂e (%{percent})<extra></extra>",
                textinfo="label+percent",
                textfont_size=12,
            ))
            fig3.update_layout(
                height=320, margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="white",
                showlegend=False,
                font=dict(family="Inter, Helvetica, sans-serif", size=12),
            )
            st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### Credits Issued by Country")
    if not isf.empty:
        by_country = (
            isf.groupby("country")["credits_issued"].sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        fig4 = go.Figure(go.Bar(
            x=by_country["country"],
            y=by_country["credits_issued"],
            marker_color="#6366F1",
            hovertemplate="%{x}<br>%{y:,.0f} tCO₂e<extra></extra>",
            text=[_fmt_credits(v) for v in by_country["credits_issued"]],
            textposition="outside",
        ))
        fig4.update_layout(
            yaxis=dict(tickformat=",.0f", gridcolor="#F1F5F9"),
            plot_bgcolor="white", paper_bgcolor="white",
            height=320, margin=dict(l=10, r=10, t=10, b=30),
            font=dict(family="Inter, Helvetica, sans-serif", size=12),
        )
        st.plotly_chart(fig4, use_container_width=True)

    # Retirement rate
    st.markdown("### Retirement Rate by Project Type")
    if not isf.empty:
        type_agg = (
            isf.groupby("type")
            .agg(issued=("credits_issued", "sum"), retired=("credits_retired", "sum"))
            .reset_index()
        )
        type_agg["retirement_rate"] = (type_agg["retired"] / type_agg["issued"] * 100).round(1)
        type_agg = type_agg.sort_values("retirement_rate", ascending=False)
        colours5 = [TYPE_COLOURS.get(t, "#94A3B8") for t in type_agg["type"]]
        fig5 = go.Figure(go.Bar(
            x=type_agg["type"],
            y=type_agg["retirement_rate"],
            marker_color=colours5,
            hovertemplate="%{x}<br>Retirement rate: %{y:.1f}%<extra></extra>",
            text=[f"{v:.1f}%" for v in type_agg["retirement_rate"]],
            textposition="outside",
        ))
        fig5.update_layout(
            yaxis=dict(range=[0, 115], ticksuffix="%", gridcolor="#F1F5F9"),
            plot_bgcolor="white", paper_bgcolor="white",
            height=300, margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family="Inter, Helvetica, sans-serif", size=12),
        )
        st.plotly_chart(fig5, use_container_width=True)


# ── Projects tab ───────────────────────────────────────────────────────────────

def _render_projects(pf: pd.DataFrame) -> None:
    st.markdown(f"### {len(pf)} Project{'s' if len(pf) != 1 else ''}")

    search = st.text_input("Search projects", placeholder="Name, country, type…", key="proj_search")
    if search:
        mask = (
            pf["name"].str.contains(search, case=False, na=False)
            | pf["country"].str.contains(search, case=False, na=False)
            | pf["type"].str.contains(search, case=False, na=False)
            | pf["id"].str.contains(search, case=False, na=False)
        )
        pf = pf[mask]

    if pf.empty:
        st.info("No projects match the current filters.")
        return

    # Project cards
    for _, row in pf.iterrows():
        with st.expander(
            f"**{row['id']}** – {row['name']}  {_status_badge(row['status'])}",
            expanded=False,
        ):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**Country:** {row['country']}")
                st.markdown(f"**Type:** {row['type']}")
                st.markdown(f"**Standard:** {row['standard']}")
            with c2:
                area = f"{row['area_ha']:,.0f} ha" if pd.notna(row["area_ha"]) and row["area_ha"] else "N/A"
                st.markdown(f"**Area:** {area}")
                st.markdown(f"**Vintage period:** {row['vintage_start']} – {row['vintage_end']}")
                st.markdown(
                    f"**Status:** <span style='font-weight:600'>{row['status']}</span>",
                    unsafe_allow_html=True,
                )
            with c3:
                st.metric("Total Issued", _fmt_credits(row["total_issued"]) + " tCO₂e")
                st.metric("Total Retired", _fmt_credits(row["total_retired"]) + " tCO₂e")
                st.metric("Outstanding", _fmt_credits(row["credits_outstanding"]) + " tCO₂e")
            st.caption(row["description"])

    # Summary table
    st.markdown("### Summary Table")
    display_cols = ["id", "name", "type", "country", "standard", "status",
                    "total_issued", "total_retired", "credits_outstanding"]
    table_df = pf[display_cols].copy()
    table_df.columns = [
        "ID", "Name", "Type", "Country", "Standard", "Status",
        "Issued (tCO₂e)", "Retired (tCO₂e)", "Outstanding (tCO₂e)",
    ]

    def _colour_status(val: str) -> str:
        cfg = STATUS_COLOURS.get(val, {"bg": "#F3F4F6", "text": "#6B7280"})
        return f"background-color:{cfg['bg']};color:{cfg['text']}"

    styled = (
        table_df.style
        .applymap(_colour_status, subset=["Status"])
        .format({
            "Issued (tCO₂e)": "{:,.0f}",
            "Retired (tCO₂e)": "{:,.0f}",
            "Outstanding (tCO₂e)": "{:,.0f}",
        })
        .set_properties(**{"text-align": "left"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


# ── Issuances tab ──────────────────────────────────────────────────────────────

def _render_issuances(isf: pd.DataFrame) -> None:
    st.markdown("### Issuance Records")

    if isf.empty:
        st.info("No issuance data for current filters.")
        return

    # Stacked area: issuances over time by project type
    st.markdown("#### Cumulative Issuances by Type Over Time")
    pivot = (
        isf.groupby(["vintage_year", "type"])["credits_issued"]
        .sum()
        .reset_index()
    )
    types_ordered = (
        pivot.groupby("type")["credits_issued"].sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    fig = go.Figure()
    for ptype in types_ordered:
        sub = pivot[pivot["type"] == ptype].sort_values("vintage_year")
        fig.add_trace(go.Scatter(
            x=sub["vintage_year"], y=sub["credits_issued"],
            mode="lines+markers",
            name=ptype,
            stackgroup="one",
            line=dict(color=TYPE_COLOURS.get(ptype, "#94A3B8"), width=2),
            hovertemplate=f"{ptype}<br>Vintage %{{x}}<br>%{{y:,.0f}} tCO₂e<extra></extra>",
        ))
    fig.update_layout(
        xaxis=dict(title="Vintage Year", tickmode="linear", dtick=1),
        yaxis=dict(title="tCO₂e", tickformat=",.0f", gridcolor="#F1F5F9"),
        plot_bgcolor="white", paper_bgcolor="white",
        height=360, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=-0.18),
        font=dict(family="Inter, Helvetica, sans-serif", size=12),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Raw issuance table
    st.markdown("#### Issuance Detail")
    show_df = isf[["project_id", "project_name", "vintage_year", "type",
                    "country", "standard", "credits_issued", "credits_retired"]].copy()
    show_df["retirement_rate"] = (
        show_df["credits_retired"] / show_df["credits_issued"] * 100
    ).round(1)
    show_df.columns = [
        "Project ID", "Project Name", "Vintage", "Type",
        "Country", "Standard", "Issued (tCO₂e)", "Retired (tCO₂e)", "Retirement %",
    ]
    show_df = show_df.sort_values(["Vintage", "Issued (tCO₂e)"], ascending=[False, False])

    styled_iso = (
        show_df.style
        .format({
            "Issued (tCO₂e)": "{:,.0f}",
            "Retired (tCO₂e)": "{:,.0f}",
            "Retirement %": "{:.1f}%",
        })
        .bar(subset=["Retirement %"], color="#BBF7D0", vmin=0, vmax=100)
        .set_properties(**{"text-align": "left"})
    )
    st.dataframe(styled_iso, use_container_width=True, hide_index=True)

    # Download
    csv = show_df.to_csv(index=False)
    st.download_button(
        label="Download issuances CSV",
        data=csv,
        file_name="carbon_issuances.csv",
        mime="text/csv",
    )
