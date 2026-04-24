"""
Carbon Market Dashboard.

Provides an interactive view over Australian Carbon Credit Unit (ACCU) projects,
project developers (aggregators / proponents) and monthly issuances.

The dataset here is an *illustrative sample* that mirrors the shape of the
Clean Energy Regulator's public project register and issuance tables. Swap
`load_dataset()` for a real CSV / CER export when connecting live data.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st


# ── Reference data ────────────────────────────────────────────────────────────

METHODS = [
    "Human-Induced Regeneration",
    "Environmental Plantings",
    "Avoided Deforestation",
    "Savanna Fire Management",
    "Landfill Gas",
    "Soil Carbon (measurement)",
    "Plantation Forestry",
    "Industrial Fugitives",
    "Beef Cattle Herd Management",
    "Waste Diversion (ACCM)",
]

METHOD_CATEGORY = {
    "Human-Induced Regeneration": "Vegetation",
    "Environmental Plantings": "Vegetation",
    "Avoided Deforestation": "Vegetation",
    "Plantation Forestry": "Vegetation",
    "Savanna Fire Management": "Savanna",
    "Landfill Gas": "Waste & Energy",
    "Waste Diversion (ACCM)": "Waste & Energy",
    "Soil Carbon (measurement)": "Agriculture",
    "Beef Cattle Herd Management": "Agriculture",
    "Industrial Fugitives": "Industrial",
}

STATES = ["NSW", "QLD", "WA", "VIC", "SA", "NT", "TAS", "ACT"]

DEVELOPERS = [
    "GreenCollar",
    "Corporate Carbon",
    "Climate Friendly",
    "Select Carbon",
    "Agriprove",
    "Terra Carbon",
    "Australian Integrated Carbon",
    "RegenCo",
    "LMS Energy",
    "Edify Carbon",
    "Midday Group",
    "Savanna Solutions NT",
    "Natural Capital Partners AU",
    "Aboriginal Carbon Foundation",
    "Pollination Group",
]

STATUS_CHOICES = ["Registered", "Crediting", "Suspended", "Closed"]


# ── Sample dataset ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _ProjectSeed:
    pid: str
    name: str
    developer: str
    method: str
    state: str
    registered: date
    crediting_start: date
    crediting_years: int
    status: str
    total_accus: int        # total issued to date (tCO2-e)


def _project_seeds() -> list[_ProjectSeed]:
    """Curated illustrative sample. Totals chosen to be plausible not real."""
    seeds = [
        # Human-Induced Regeneration (large, rangelands)
        _ProjectSeed("ERF102001", "Mulga Downs HIR", "GreenCollar",
                     "Human-Induced Regeneration", "NSW",
                     date(2014, 3, 1), date(2014, 6, 1), 25, "Crediting", 1_840_000),
        _ProjectSeed("ERF102045", "Paroo Rangelands HIR", "GreenCollar",
                     "Human-Induced Regeneration", "QLD",
                     date(2015, 5, 15), date(2015, 7, 1), 25, "Crediting", 2_310_000),
        _ProjectSeed("ERF102210", "Cobar West HIR", "Corporate Carbon",
                     "Human-Induced Regeneration", "NSW",
                     date(2015, 9, 2), date(2015, 12, 1), 25, "Crediting", 1_120_000),
        _ProjectSeed("ERF103011", "Warrego Basin HIR", "Corporate Carbon",
                     "Human-Induced Regeneration", "QLD",
                     date(2016, 2, 10), date(2016, 4, 1), 25, "Crediting", 1_560_000),
        _ProjectSeed("ERF103177", "Murchison HIR", "Climate Friendly",
                     "Human-Induced Regeneration", "WA",
                     date(2016, 7, 22), date(2016, 10, 1), 25, "Crediting", 980_000),
        _ProjectSeed("ERF104052", "Bourke Plains HIR", "Climate Friendly",
                     "Human-Induced Regeneration", "NSW",
                     date(2017, 3, 1), date(2017, 6, 1), 25, "Crediting", 1_410_000),
        _ProjectSeed("ERF104234", "Gascoyne HIR", "Australian Integrated Carbon",
                     "Human-Induced Regeneration", "WA",
                     date(2017, 11, 14), date(2018, 1, 1), 25, "Crediting", 870_000),
        _ProjectSeed("ERF105099", "Maranoa Regeneration", "GreenCollar",
                     "Human-Induced Regeneration", "QLD",
                     date(2018, 4, 5), date(2018, 7, 1), 25, "Crediting", 760_000),
        _ProjectSeed("ERF105321", "Diamantina HIR", "Terra Carbon",
                     "Human-Induced Regeneration", "QLD",
                     date(2019, 1, 20), date(2019, 4, 1), 25, "Crediting", 540_000),
        _ProjectSeed("ERF106044", "Balonne HIR", "Pollination Group",
                     "Human-Induced Regeneration", "QLD",
                     date(2019, 9, 10), date(2020, 1, 1), 25, "Suspended", 180_000),

        # Environmental Plantings
        _ProjectSeed("ERF201010", "Riverina Mixed Species EP", "Select Carbon",
                     "Environmental Plantings", "NSW",
                     date(2015, 6, 1), date(2015, 9, 1), 25, "Crediting", 240_000),
        _ProjectSeed("ERF201088", "Goulburn Broken EP", "Select Carbon",
                     "Environmental Plantings", "VIC",
                     date(2016, 3, 14), date(2016, 6, 1), 25, "Crediting", 190_000),
        _ProjectSeed("ERF202101", "Wheatbelt EP", "Climate Friendly",
                     "Environmental Plantings", "WA",
                     date(2017, 8, 1), date(2017, 11, 1), 25, "Crediting", 150_000),
        _ProjectSeed("ERF203055", "Limestone Coast EP", "RegenCo",
                     "Environmental Plantings", "SA",
                     date(2018, 2, 28), date(2018, 6, 1), 25, "Crediting", 98_000),
        _ProjectSeed("ERF204012", "New England EP", "Select Carbon",
                     "Environmental Plantings", "NSW",
                     date(2019, 5, 20), date(2019, 8, 1), 25, "Crediting", 82_000),

        # Avoided Deforestation
        _ProjectSeed("ERF301003", "Darling Downs Avoided Clearing",
                     "Corporate Carbon", "Avoided Deforestation", "QLD",
                     date(2013, 11, 1), date(2014, 1, 1), 20, "Crediting", 1_250_000),
        _ProjectSeed("ERF301044", "Condamine Avoided Deforestation",
                     "Corporate Carbon", "Avoided Deforestation", "QLD",
                     date(2014, 4, 10), date(2014, 7, 1), 20, "Crediting", 960_000),
        _ProjectSeed("ERF302019", "Western NSW Avoided Clearing",
                     "GreenCollar", "Avoided Deforestation", "NSW",
                     date(2014, 9, 15), date(2015, 1, 1), 20, "Closed", 410_000),

        # Savanna Fire Management
        _ProjectSeed("ERF401002", "West Arnhem SFM", "Aboriginal Carbon Foundation",
                     "Savanna Fire Management", "NT",
                     date(2013, 1, 15), date(2013, 5, 1), 7, "Crediting", 680_000),
        _ProjectSeed("ERF401029", "Tiwi Islands SFM", "Savanna Solutions NT",
                     "Savanna Fire Management", "NT",
                     date(2014, 2, 20), date(2014, 5, 1), 7, "Crediting", 520_000),
        _ProjectSeed("ERF402007", "Kimberley SFM", "Savanna Solutions NT",
                     "Savanna Fire Management", "WA",
                     date(2015, 3, 1), date(2015, 5, 1), 7, "Crediting", 610_000),
        _ProjectSeed("ERF402089", "Cape York SFM", "Aboriginal Carbon Foundation",
                     "Savanna Fire Management", "QLD",
                     date(2016, 4, 12), date(2016, 6, 1), 7, "Crediting", 430_000),
        _ProjectSeed("ERF403110", "Gulf Country SFM", "Midday Group",
                     "Savanna Fire Management", "QLD",
                     date(2017, 2, 2), date(2017, 5, 1), 7, "Crediting", 370_000),
        _ProjectSeed("ERF404055", "Central Arnhem SFM", "Aboriginal Carbon Foundation",
                     "Savanna Fire Management", "NT",
                     date(2018, 3, 30), date(2018, 6, 1), 7, "Crediting", 290_000),

        # Landfill Gas
        _ProjectSeed("ERF501002", "Lucas Heights LFG", "LMS Energy",
                     "Landfill Gas", "NSW",
                     date(2013, 7, 1), date(2013, 9, 1), 7, "Crediting", 720_000),
        _ProjectSeed("ERF501055", "Clayton South LFG", "LMS Energy",
                     "Landfill Gas", "VIC",
                     date(2013, 10, 1), date(2014, 1, 1), 7, "Crediting", 540_000),
        _ProjectSeed("ERF502010", "Rochedale LFG", "LMS Energy",
                     "Landfill Gas", "QLD",
                     date(2014, 4, 1), date(2014, 6, 1), 7, "Crediting", 480_000),
        _ProjectSeed("ERF502088", "Red Hill LFG", "Edify Carbon",
                     "Landfill Gas", "ACT",
                     date(2015, 5, 15), date(2015, 8, 1), 7, "Crediting", 210_000),
        _ProjectSeed("ERF503004", "Wingfield LFG", "LMS Energy",
                     "Landfill Gas", "SA",
                     date(2015, 11, 10), date(2016, 2, 1), 7, "Crediting", 330_000),
        _ProjectSeed("ERF504091", "Canning Vale LFG", "Edify Carbon",
                     "Landfill Gas", "WA",
                     date(2017, 2, 1), date(2017, 5, 1), 7, "Crediting", 260_000),

        # Soil Carbon
        _ProjectSeed("ERF601010", "Monaro Soil Carbon", "Agriprove",
                     "Soil Carbon (measurement)", "NSW",
                     date(2019, 3, 1), date(2019, 7, 1), 25, "Crediting", 48_000),
        _ProjectSeed("ERF601077", "Darling Downs Soil Carbon", "Agriprove",
                     "Soil Carbon (measurement)", "QLD",
                     date(2020, 2, 14), date(2020, 6, 1), 25, "Crediting", 36_000),
        _ProjectSeed("ERF602055", "Gippsland Soil Carbon", "RegenCo",
                     "Soil Carbon (measurement)", "VIC",
                     date(2020, 9, 1), date(2021, 1, 1), 25, "Crediting", 22_000),
        _ProjectSeed("ERF603101", "Eyre Peninsula Soil Carbon", "Agriprove",
                     "Soil Carbon (measurement)", "SA",
                     date(2021, 5, 22), date(2021, 9, 1), 25, "Crediting", 14_000),
        _ProjectSeed("ERF604023", "Liverpool Plains Soil", "Natural Capital Partners AU",
                     "Soil Carbon (measurement)", "NSW",
                     date(2022, 1, 18), date(2022, 6, 1), 25, "Crediting", 9_500),

        # Plantation Forestry
        _ProjectSeed("ERF701005", "Green Triangle Pine", "Edify Carbon",
                     "Plantation Forestry", "SA",
                     date(2014, 6, 1), date(2014, 9, 1), 25, "Crediting", 320_000),
        _ProjectSeed("ERF701044", "Tumut Softwood Plantation", "Edify Carbon",
                     "Plantation Forestry", "NSW",
                     date(2015, 3, 10), date(2015, 6, 1), 25, "Crediting", 280_000),
        _ProjectSeed("ERF702029", "Tasmanian Plantation", "Terra Carbon",
                     "Plantation Forestry", "TAS",
                     date(2016, 8, 1), date(2016, 11, 1), 25, "Crediting", 180_000),

        # Industrial Fugitives
        _ProjectSeed("ERF801001", "Bowen Basin Coal Mine Waste Gas",
                     "Corporate Carbon", "Industrial Fugitives", "QLD",
                     date(2014, 2, 1), date(2014, 5, 1), 12, "Crediting", 1_180_000),
        _ProjectSeed("ERF801022", "Hunter Valley Mine Methane",
                     "Corporate Carbon", "Industrial Fugitives", "NSW",
                     date(2015, 1, 10), date(2015, 4, 1), 12, "Crediting", 940_000),
        _ProjectSeed("ERF802044", "Surat Basin Fugitives",
                     "Midday Group", "Industrial Fugitives", "QLD",
                     date(2016, 6, 1), date(2016, 9, 1), 12, "Crediting", 410_000),

        # Beef Herd Management
        _ProjectSeed("ERF901013", "Top End Beef Herd", "Midday Group",
                     "Beef Cattle Herd Management", "NT",
                     date(2017, 9, 1), date(2018, 1, 1), 7, "Crediting", 58_000),
        _ProjectSeed("ERF902021", "Channel Country Beef", "Midday Group",
                     "Beef Cattle Herd Management", "QLD",
                     date(2018, 6, 14), date(2018, 10, 1), 7, "Crediting", 41_000),

        # Waste diversion
        _ProjectSeed("ERFA01003", "Western Sydney ACCM", "LMS Energy",
                     "Waste Diversion (ACCM)", "NSW",
                     date(2020, 4, 1), date(2020, 8, 1), 7, "Crediting", 72_000),
        _ProjectSeed("ERFA02011", "Brisbane ACCM", "LMS Energy",
                     "Waste Diversion (ACCM)", "QLD",
                     date(2021, 2, 10), date(2021, 6, 1), 7, "Crediting", 54_000),
    ]
    return seeds


def _synthesise_monthly(seeds: Iterable[_ProjectSeed]) -> pd.DataFrame:
    """Spread each project's total ACCUs across months between crediting start
    and the end of 2025, weighted by a smooth S-curve so charts look realistic.
    Deterministic via a fixed seed.
    """
    rng = random.Random(42)
    rows = []
    end = date(2025, 12, 1)

    for s in seeds:
        start = s.crediting_start
        months = (end.year - start.year) * 12 + (end.month - start.month) + 1
        if months <= 0:
            continue
        # S-curve weights so issuances ramp up then plateau
        weights = []
        for i in range(months):
            x = (i + 0.5) / months
            w = 1 / (1 + math.exp(-8 * (x - 0.35)))
            # add mild noise
            w *= 0.75 + rng.random() * 0.5
            weights.append(w)
        # Projects don't issue every month — zero-out ~60% of early months
        for i in range(months):
            if rng.random() < 0.55:
                weights[i] = 0.0
        total_w = sum(weights) or 1.0
        total = s.total_accus
        issued = 0
        for i, w in enumerate(weights):
            yr = start.year + (start.month - 1 + i) // 12
            mo = (start.month - 1 + i) % 12 + 1
            amount = int(round(total * w / total_w))
            issued += amount
            if amount == 0:
                continue
            rows.append({
                "project_id": s.pid,
                "project_name": s.name,
                "developer": s.developer,
                "method": s.method,
                "state": s.state,
                "issuance_month": pd.Timestamp(year=yr, month=mo, day=1),
                "accus_issued": amount,
            })
        # Reconcile rounding drift onto the last non-zero month
        drift = total - issued
        if drift != 0 and rows and rows[-1]["project_id"] == s.pid:
            rows[-1]["accus_issued"] = max(0, rows[-1]["accus_issued"] + drift)

    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (projects_df, issuances_df)."""
    seeds = _project_seeds()
    projects = pd.DataFrame([{
        "project_id": s.pid,
        "project_name": s.name,
        "developer": s.developer,
        "method": s.method,
        "method_category": METHOD_CATEGORY[s.method],
        "state": s.state,
        "registered": pd.Timestamp(s.registered),
        "crediting_start": pd.Timestamp(s.crediting_start),
        "crediting_years": s.crediting_years,
        "status": s.status,
        "total_accus_issued": s.total_accus,
    } for s in seeds])
    issuances = _synthesise_monthly(seeds)
    return projects, issuances


# ── Filtering ─────────────────────────────────────────────────────────────────


def _apply_filters(
    projects: pd.DataFrame,
    issuances: pd.DataFrame,
    methods: list[str],
    states: list[str],
    developers: list[str],
    year_range: tuple[int, int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = projects.copy()
    if methods:
        p = p[p["method"].isin(methods)]
    if states:
        p = p[p["state"].isin(states)]
    if developers:
        p = p[p["developer"].isin(developers)]

    i = issuances[issuances["project_id"].isin(p["project_id"])].copy()
    i = i[
        (i["issuance_month"].dt.year >= year_range[0])
        & (i["issuance_month"].dt.year <= year_range[1])
    ]

    # Recompute each project's issuance total under the active year filter so
    # headline metrics and tables stay consistent.
    totals_in_window = (
        i.groupby("project_id")["accus_issued"].sum().rename("accus_in_window")
    )
    p = p.join(totals_in_window, on="project_id").fillna({"accus_in_window": 0})
    p["accus_in_window"] = p["accus_in_window"].astype(int)
    return p, i


# ── Rendering helpers ─────────────────────────────────────────────────────────


def _fmt_accu(n: float) -> str:
    n = float(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return f"{n:,.0f}"


def _metric_row(projects: pd.DataFrame, issuances: pd.DataFrame) -> None:
    total_issued = int(issuances["accus_issued"].sum())
    active = int((projects["status"] == "Crediting").sum())
    devs = projects["developer"].nunique()
    avg_per_project = total_issued / max(len(projects), 1)

    latest = issuances["issuance_month"].max() if not issuances.empty else None
    latest_label = latest.strftime("%b %Y") if latest is not None else "–"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ACCUs issued (filtered)", _fmt_accu(total_issued))
    c2.metric("Projects in view", f"{len(projects):,}")
    c3.metric("Active (crediting)", f"{active:,}")
    c4.metric("Distinct developers", f"{devs:,}")
    c5.metric("Avg ACCUs / project", _fmt_accu(avg_per_project))
    st.caption(f"Latest issuance month in view: **{latest_label}**")


def _chart_issuance_trend(issuances: pd.DataFrame) -> None:
    if issuances.empty:
        st.info("No issuances match the current filters.")
        return
    monthly = (
        issuances.groupby("issuance_month")["accus_issued"].sum().reset_index()
    )
    fig = px.area(
        monthly, x="issuance_month", y="accus_issued",
        title="Monthly ACCU issuances",
        labels={"issuance_month": "Month", "accus_issued": "ACCUs issued"},
    )
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_by_method(issuances: pd.DataFrame) -> None:
    if issuances.empty:
        return
    by_method = (
        issuances.groupby("method")["accus_issued"].sum()
        .sort_values(ascending=True).reset_index()
    )
    fig = px.bar(
        by_method, x="accus_issued", y="method", orientation="h",
        title="ACCUs issued by method",
        labels={"accus_issued": "ACCUs issued", "method": ""},
    )
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_by_state(issuances: pd.DataFrame) -> None:
    if issuances.empty:
        return
    by_state = (
        issuances.groupby("state")["accus_issued"].sum()
        .sort_values(ascending=False).reset_index()
    )
    fig = px.bar(
        by_state, x="state", y="accus_issued",
        title="ACCUs issued by state / territory",
        labels={"accus_issued": "ACCUs issued", "state": ""},
    )
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_status_mix(projects: pd.DataFrame) -> None:
    if projects.empty:
        return
    mix = projects["status"].value_counts().reset_index()
    mix.columns = ["status", "count"]
    fig = px.pie(mix, names="status", values="count", title="Project status mix",
                 hole=0.45)
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_top_developers(projects: pd.DataFrame) -> None:
    if projects.empty:
        return
    top = (
        projects.groupby("developer")["accus_in_window"].sum()
        .sort_values(ascending=True).tail(10).reset_index()
    )
    fig = px.bar(
        top, x="accus_in_window", y="developer", orientation="h",
        title="Top developers by ACCUs issued (filtered window)",
        labels={"accus_in_window": "ACCUs issued", "developer": ""},
    )
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ── Tabs ──────────────────────────────────────────────────────────────────────


def _tab_overview(projects: pd.DataFrame, issuances: pd.DataFrame) -> None:
    _metric_row(projects, issuances)
    st.markdown("---")
    _chart_issuance_trend(issuances)
    col1, col2 = st.columns(2)
    with col1:
        _chart_by_method(issuances)
        _chart_status_mix(projects)
    with col2:
        _chart_by_state(issuances)
        _chart_top_developers(projects)


def _tab_developers(projects: pd.DataFrame, issuances: pd.DataFrame) -> None:
    if projects.empty:
        st.info("No developers match the current filters.")
        return

    summary = (
        projects.groupby("developer")
        .agg(
            projects=("project_id", "count"),
            active=("status", lambda s: int((s == "Crediting").sum())),
            states=("state", lambda s: ", ".join(sorted(set(s)))),
            methods=("method", lambda m: ", ".join(sorted(set(m)))),
            accus=("accus_in_window", "sum"),
        )
        .reset_index()
        .sort_values("accus", ascending=False)
    )
    summary["accus"] = summary["accus"].astype(int)

    st.markdown("#### Developer league table")
    st.dataframe(
        summary.rename(columns={
            "developer": "Developer",
            "projects": "Projects",
            "active": "Active",
            "states": "States",
            "methods": "Methods",
            "accus": "ACCUs (window)",
        }),
        hide_index=True, use_container_width=True,
    )

    st.markdown("---")
    st.markdown("#### Developer profile")
    chosen = st.selectbox(
        "Select a developer",
        summary["developer"].tolist(),
        key="cm_dev_select",
    )
    dev_projects = projects[projects["developer"] == chosen]
    dev_issuances = issuances[issuances["developer"] == chosen]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projects", f"{len(dev_projects):,}")
    c2.metric("Active", f"{int((dev_projects['status']=='Crediting').sum()):,}")
    c3.metric("ACCUs (window)", _fmt_accu(dev_projects["accus_in_window"].sum()))
    c4.metric("Methods used", f"{dev_projects['method'].nunique():,}")

    if not dev_issuances.empty:
        monthly = (
            dev_issuances.groupby("issuance_month")["accus_issued"]
            .sum().reset_index()
        )
        fig = px.bar(
            monthly, x="issuance_month", y="accus_issued",
            title=f"Monthly issuances – {chosen}",
            labels={"issuance_month": "Month", "accus_issued": "ACCUs"},
        )
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"**Projects operated by {chosen}**")
    st.dataframe(
        dev_projects[[
            "project_id", "project_name", "method", "state",
            "status", "crediting_start", "accus_in_window",
        ]].rename(columns={
            "project_id": "Project ID",
            "project_name": "Project",
            "method": "Method",
            "state": "State",
            "status": "Status",
            "crediting_start": "Crediting from",
            "accus_in_window": "ACCUs (window)",
        }),
        hide_index=True, use_container_width=True,
    )


def _tab_projects(projects: pd.DataFrame, issuances: pd.DataFrame) -> None:
    if projects.empty:
        st.info("No projects match the current filters.")
        return

    search = st.text_input(
        "Search project name / ID / developer",
        key="cm_project_search", placeholder="e.g. Mulga, ERF102, GreenCollar",
    )
    table = projects.copy()
    if search.strip():
        q = search.strip().lower()
        mask = (
            table["project_name"].str.lower().str.contains(q)
            | table["project_id"].str.lower().str.contains(q)
            | table["developer"].str.lower().str.contains(q)
        )
        table = table[mask]

    st.caption(f"{len(table):,} project(s) in view")
    st.dataframe(
        table[[
            "project_id", "project_name", "developer", "method",
            "method_category", "state", "status",
            "registered", "crediting_start", "crediting_years",
            "accus_in_window", "total_accus_issued",
        ]].rename(columns={
            "project_id": "Project ID",
            "project_name": "Project",
            "developer": "Developer",
            "method": "Method",
            "method_category": "Category",
            "state": "State",
            "status": "Status",
            "registered": "Registered",
            "crediting_start": "Crediting from",
            "crediting_years": "Period (yrs)",
            "accus_in_window": "ACCUs (window)",
            "total_accus_issued": "ACCUs (to date)",
        }).sort_values("ACCUs (window)", ascending=False),
        hide_index=True, use_container_width=True, height=460,
    )

    st.download_button(
        "Download projects CSV",
        data=table.to_csv(index=False).encode("utf-8"),
        file_name="accu_projects.csv",
        mime="text/csv",
    )


def _tab_issuances(issuances: pd.DataFrame) -> None:
    if issuances.empty:
        st.info("No issuances match the current filters.")
        return

    st.markdown("#### Issuance trend")
    grain = st.radio(
        "Aggregate by", ["Month", "Quarter", "Year"],
        horizontal=True, key="cm_grain",
    )
    df = issuances.copy()
    if grain == "Month":
        df["bucket"] = df["issuance_month"]
    elif grain == "Quarter":
        df["bucket"] = df["issuance_month"].dt.to_period("Q").dt.to_timestamp()
    else:
        df["bucket"] = df["issuance_month"].dt.to_period("Y").dt.to_timestamp()

    by_bucket_method = (
        df.groupby(["bucket", "method"])["accus_issued"].sum().reset_index()
    )
    fig = px.bar(
        by_bucket_method, x="bucket", y="accus_issued", color="method",
        title=f"ACCU issuances by {grain.lower()} and method",
        labels={"bucket": grain, "accus_issued": "ACCUs issued", "method": "Method"},
    )
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10), barmode="stack")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Issuance line items")
    recent = issuances.sort_values("issuance_month", ascending=False).head(500)
    st.dataframe(
        recent.rename(columns={
            "project_id": "Project ID",
            "project_name": "Project",
            "developer": "Developer",
            "method": "Method",
            "state": "State",
            "issuance_month": "Month",
            "accus_issued": "ACCUs",
        }),
        hide_index=True, use_container_width=True, height=420,
    )
    st.caption("Showing the 500 most recent issuance rows in view.")

    st.download_button(
        "Download issuances CSV",
        data=issuances.to_csv(index=False).encode("utf-8"),
        file_name="accu_issuances.csv",
        mime="text/csv",
    )


# ── Public entrypoint ─────────────────────────────────────────────────────────


def render() -> None:
    st.title("🌱 Carbon Market Dashboard – ACCU scheme")
    st.caption(
        "Project developers, projects and Australian Carbon Credit Unit (ACCU) "
        "issuances. Sample dataset for illustration; wire a live CER export in "
        "`modules/carbon_market.py::load_dataset` to use real data."
    )

    projects_all, issuances_all = load_dataset()

    with st.expander("Filters", expanded=True):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 3])
        with col1:
            f_methods = st.multiselect(
                "Method", sorted(projects_all["method"].unique()),
                key="cm_f_method",
            )
        with col2:
            f_states = st.multiselect(
                "State", sorted(projects_all["state"].unique()),
                key="cm_f_state",
            )
        with col3:
            f_devs = st.multiselect(
                "Developer", sorted(projects_all["developer"].unique()),
                key="cm_f_dev",
            )
        with col4:
            y_min = int(issuances_all["issuance_month"].dt.year.min())
            y_max = int(issuances_all["issuance_month"].dt.year.max())
            f_years = st.slider(
                "Issuance year range", min_value=y_min, max_value=y_max,
                value=(y_min, y_max), key="cm_f_years",
            )

    projects, issuances = _apply_filters(
        projects_all, issuances_all, f_methods, f_states, f_devs, f_years,
    )

    tabs = st.tabs(["Overview", "Developers", "Projects", "Issuances"])
    with tabs[0]:
        _tab_overview(projects, issuances)
    with tabs[1]:
        _tab_developers(projects, issuances)
    with tabs[2]:
        _tab_projects(projects, issuances)
    with tabs[3]:
        _tab_issuances(issuances)
