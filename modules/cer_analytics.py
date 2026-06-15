"""
cer_analytics.py
Python analytics layer for CER data.
Mirrors src/lib/cer/analytics.ts — drop this file into your Streamlit app,
call set_data_dir() pointing at the pollination-carbon-tracker/data/ folder,
and use any function below.

Streamlit tip: wrap loaders with @st.cache_data for session caching:
    import streamlit as st
    load_project_register = st.cache_data(cer_analytics.load_project_register)
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

# ── Path configuration ─────────────────────────────────────────────────────────

_DATA_DIR: Path | None = None
_CACHE: dict[str, Any] = {}


def set_data_dir(path: str | Path) -> None:
    """Point analytics at a specific data/ directory and clear the cache."""
    global _DATA_DIR
    _DATA_DIR = Path(path)
    _CACHE.clear()


def clear_cache() -> None:
    _CACHE.clear()


def _data_dir() -> Path:
    if _DATA_DIR is not None:
        return _DATA_DIR
    import os
    env = os.environ.get("CER_DATA_DIR")
    if env:
        return Path(env)
    # Walk up from this file to find a data/ sibling
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data"
        if candidate.is_dir():
            return candidate
    raise RuntimeError(
        "Cannot find CER data directory. "
        "Call set_data_dir() or set the CER_DATA_DIR env var."
    )


def _latest(pattern: str) -> Path:
    """Return the most recently dated path matching a glob under data/."""
    matches = sorted(glob.glob(str(_data_dir() / pattern)))
    if not matches:
        raise FileNotFoundError(f"No files found: {_data_dir() / pattern}")
    return Path(matches[-1])


def _load_once(key: str, loader):
    if key not in _CACHE:
        _CACHE[key] = loader()
    return _CACHE[key]


# ── Constants ──────────────────────────────────────────────────────────────────

METHOD_ORDER = [
    "Vegetation",
    "Waste",
    "Savanna Fire Management",
    "Energy Efficiency",
    "Industrial Fugitives",
    "Agriculture",
    "Carbon Capture",
    "Transport",
    "Facilities",
]

# Maps Method Type strings (case-insensitive) → snake_case key
_METHOD_KEY: dict[str, str] = {
    "vegetation": "vegetation",
    "waste": "waste",
    "savanna fire management": "savanna_fire",
    "savanna fire": "savanna_fire",
    "energy efficiency": "energy_efficiency",
    "industrial fugitives": "industrial_fugitives",
    "agriculture": "agriculture",
    "carbon capture": "carbon_capture",
    "transport": "transport",
    "facilities": "facilities",
}

FY_COL_RE = re.compile(r"Financial Year (\d{4})/(\d{2})")

ACCU_DISCLOSURE_THRESHOLD = 0.3


# ── Formatting helpers ─────────────────────────────────────────────────────────

def fmt_k(n: float) -> str:
    """1_500_000 → '1.5M', 42_000 → '42.0K', 999 → '999'"""
    a = abs(n)
    if a >= 1e6:
        return f"{n / 1e6:.1f}M"
    if a >= 1e3:
        return f"{n / 1e3:.1f}K"
    return str(round(n))


def _fy_label(start_year: int) -> str:
    """2024 → 'FY24/25'"""
    return f"FY{str(start_year)[2:]}/{str(start_year + 1)[2:]}"


def _method_key(method_type: str) -> str:
    return _METHOD_KEY.get(str(method_type).strip().lower(), "other")


# ── Parsing utilities ──────────────────────────────────────────────────────────

def _parse_num(val) -> float | None:
    if pd.isna(val) or str(val).strip() in ("-", "", "n/a", "N/A", " -   "):
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return None


def _parse_int0(val) -> int:
    n = _parse_num(val)
    return int(n) if n is not None and pd.notna(n) else 0


def _parse_aus_date(val) -> pd.Timestamp | None:
    s = str(val).strip() if pd.notna(val) else ""
    if not s or s.lower() in ("-", "n/a"):
        return None
    try:
        return pd.to_datetime(s, dayfirst=True)
    except Exception:
        return None


# ── Data loaders ──────────────────────────────────────────────────────────────


def load_project_register() -> pd.DataFrame:
    """
    Parses the most recent CER project register CSV.
    Key output columns (all others from the raw CSV are preserved):
      project_id, proponent, method, method_type, state, revoked, contracted,
      accus_issued, registered_date, registered_ym
    Plus all FY issuance columns, e.g.:
      fy_2014, fy_2015, … (ACCUs issued in that financial year, 0 if blank)
    """
    return _load_once("project_register", _load_project_register)


def _load_project_register() -> pd.DataFrame:
    path = _latest("raw/cer/accu/project-register/*/project-register.csv")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = df.columns.str.strip()

    # Aliases
    df["project_id"] = df["Project ID"].str.strip()
    df["proponent"] = df["Project Proponent"].str.strip()
    df["method"] = df["Method"].str.strip()
    df["method_type"] = df["Method Type"].str.strip()
    df["state"] = df["Project location"].str.strip()
    df["accus_issued"] = df["ACCUs Total units issued"].apply(_parse_int0)
    df["registered_date"] = df["Date Project Registered"].apply(_parse_aus_date)
    df["registered_ym"] = df["registered_date"].apply(
        lambda d: d.strftime("%Y-%m") if pd.notna(d) else None
    )

    def _to_bool(v):
        return str(v).strip().lower() == "yes" if pd.notna(v) else False

    df["revoked"] = df["Project revoked"].apply(_to_bool)
    df["contracted"] = df.apply(
        lambda r: _to_bool(r.get("Contracted on"))
        or str(r.get("Contract ID", "")).strip().upper().startswith("CAC"),
        axis=1,
    )

    # Parse all FY issuance columns → fy_YYYY (e.g. fy_2024 = FY2024/25)
    for col in df.columns:
        m = FY_COL_RE.search(col)
        if m and col.startswith("ACCUs"):
            yr = int(m.group(1))
            df[f"fy_{yr}"] = df[col].apply(_parse_int0)

    return df


def load_voluntary_cancellations() -> pd.DataFrame:
    """
    Parses the ANREU voluntary cancellations CSV.
    Output columns: date, entity, units, unit_type, year_month
    """
    return _load_once("voluntary_cancellations", _load_voluntary_cancellations)


def _load_voluntary_cancellations() -> pd.DataFrame:
    path = _latest("raw/cer/anreu/voluntary-cancellations/*/voluntary-cancellations.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    df["date"] = df["Date of transaction"].apply(_parse_aus_date)
    df = df[df["date"].notna()].copy()
    df["entity"] = df["Entity name"].str.strip()
    df = df[df["entity"] != "Commonwealth Holding Account"].copy()
    df["units"] = df["Number of units"].apply(_parse_int0)
    df["unit_type"] = df["Unit type"].str.strip()
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    return df.reset_index(drop=True)


def load_facilities() -> pd.DataFrame:
    """
    Parses the Safeguard baselines-and-emissions CSV.
    Output columns: name, responsible_emitter, state, anzsic_name, anzsic_code,
      erc, baseline, covered_emissions, accus_surrendered, smcs_surrendered,
      net_emissions, net_position, … (all numeric fields)
    """
    return _load_once("facilities", _load_facilities)


def _load_facilities() -> pd.DataFrame:
    path = _latest("raw/cer/safeguard/*/baselines-and-emissions.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    str_map = {
        "Facility name": "name",
        "Responsible emitter": "responsible_emitter",
        "State/Territory of operation": "state",
        "Notes": "notes",
    }
    for raw, alias in str_map.items():
        if raw in df.columns:
            df[alias] = df[raw].str.strip()

    num_map = {
        "ERC": "erc",
        "Baseline emissions number": "baseline",
        "Covered emissions": "covered_emissions",
        "Borrowing adjustment amount": "borrowing_adjustment",
        "ACCUs issued": "accus_issued",
        "ACCUs deemed surrendered": "accus_deemed_surrendered",
        "ACCUs surrendered": "accus_surrendered",
        "SMCs surrendered": "smcs_surrendered",
        "Net emissions number": "net_emissions",
        "Net position number": "net_position",
        "SMCs issued": "smcs_issued",
        "Units relinquished": "units_relinquished",
        "Cumulative MYMP net emissions number": "cumulative_mymp_net_emissions",
        "Cumulative MYMP net position number": "cumulative_mymp_net_position",
        "GHG Carbon dioxide": "ghg_co2",
        "GHG Methane": "ghg_ch4",
        "GHG Nitrous oxide": "ghg_n2o",
        "GHG Other": "ghg_other",
    }
    for raw, alias in num_map.items():
        if raw in df.columns:
            df[alias] = df[raw].apply(_parse_num)

    anzsic = df.get("ANZSIC", pd.Series(dtype=str)).str.strip()
    df["anzsic_name"] = anzsic.str.extract(r"^(.+?)\s*\(\d+\)\s*$")[0].fillna(anzsic)
    df["anzsic_code"] = anzsic.str.extract(r"\((\d+)\)\s*$")[0]

    return df.reset_index(drop=True)


def load_surrender_methods() -> pd.DataFrame:
    """
    Parses the Safeguard ACCU surrender methods CSV.
    Output columns: facility_name, responsible_emitter, determination, method_type, quantity
    """
    return _load_once("surrender_methods", _load_surrender_methods)


def _load_surrender_methods() -> pd.DataFrame:
    path = _latest("raw/cer/safeguard/*/accu-surrender-methods.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    df["facility_name"] = df["Facility name"].str.strip()
    df["responsible_emitter"] = df["Responsible emitter"].str.strip()
    df["determination"] = df["ACCU methodology determination"].str.strip()
    df["method_type"] = df["ACCU method type"].str.strip()
    df["quantity"] = df["Quantity surrendered"].apply(_parse_int0)
    return df.reset_index(drop=True)


def load_qcmr() -> dict[str, pd.DataFrame]:
    """
    Loads the processed QCMR JSON series as DataFrames.
    Returns dict with keys:
      holdings           — figure-1-1: ACCU holdings by entity type per quarter
      issuance           — figure-1-2: ACCU issuance by method per quarter
      cancellations      — figure-1-4: Annual/quarterly cancellations by type
      safeguard_surrenders — figure-1-6: Safeguard ACCU/SMC surrenders per quarter
      smc_holdings       — figure-1-7: SMC holdings by entity type per quarter
    """
    return _load_once("qcmr", _load_qcmr)


def _load_qcmr() -> dict[str, pd.DataFrame]:
    base = _latest("processed/cer/qcmr/*/figure-1-1.json").parent

    def load(name: str) -> pd.DataFrame:
        with open(base / name, encoding="utf-8-sig") as f:
            return pd.DataFrame(json.load(f)["rows"])

    return {
        "holdings": load("figure-1-1.json"),
        "issuance": load("figure-1-2.json"),
        "cancellations": load("figure-1-4.json"),
        "safeguard_surrenders": load("figure-1-6.json"),
        "smc_holdings": load("figure-1-7.json"),
    }


# ── Safeguard KPIs ─────────────────────────────────────────────────────────────


def build_kpis() -> dict:
    """
    Safeguard facility-level KPIs.
    Returns dict with keys:
      facility_count, emitter_count, total_baseline, total_covered,
      total_surrendered, national_gap, above_baseline_count, heavy_accu_count
    """
    df = load_facilities()
    baseline = df["baseline"].fillna(0)
    covered = df["covered_emissions"].fillna(0)
    accus = df["accus_surrendered"].fillna(0)
    smcs = df["smcs_surrendered"].fillna(0)
    surrendered = accus + smcs

    return {
        "facility_count": len(df),
        "emitter_count": df["responsible_emitter"].nunique(),
        "total_baseline": baseline.sum(),
        "total_covered": covered.sum(),
        "total_surrendered": surrendered.sum(),
        "national_gap": covered.sum() - surrendered.sum(),
        "above_baseline_count": int((covered > baseline).sum()),
        "heavy_accu_count": int(
            (accus >= ACCU_DISCLOSURE_THRESHOLD * baseline.replace(0, float("nan"))).sum()
        ),
    }


def build_state_breakdown() -> pd.DataFrame:
    """
    Safeguard emissions aggregated by state.
    Returns DataFrame with columns: state, baseline, covered, surrendered, facilities
    """
    df = load_facilities()
    g = (
        df.groupby("state")
        .agg(
            baseline=("baseline", "sum"),
            covered=("covered_emissions", "sum"),
            surrendered_accus=("accus_surrendered", "sum"),
            surrendered_smcs=("smcs_surrendered", "sum"),
            facilities=("name", "count"),
        )
        .reset_index()
    )
    g["surrendered"] = g["surrendered_accus"] + g["surrendered_smcs"]
    return g.sort_values("covered", ascending=False).reset_index(drop=True)


def build_emitter_by_method_matrix(top_n: int = 15, method_type: str | None = None) -> dict:
    """
    Cross-tab of responsible emitters (rows) × method types (columns) by quantity surrendered.
    Returns dict with keys: method_types, rows (list of dicts), column_totals, grand_total.
    """
    df = load_surrender_methods()
    if method_type:
        df = df[df["method_type"] == method_type]

    pivot = (
        df.groupby(["responsible_emitter", "method_type"])["quantity"]
        .sum()
        .unstack(fill_value=0)
    )
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=False).head(top_n)

    method_types = [m for m in METHOD_ORDER if m in pivot.columns]
    rows = [
        {
            "emitter": idx,
            "by_method": {m: int(row.get(m, 0)) for m in method_types},
            "total": int(row["total"]),
        }
        for idx, row in pivot.iterrows()
    ]
    column_totals = {m: int(pivot[m].sum()) for m in method_types if m in pivot.columns}
    grand_total = int(pivot["total"].sum())

    return {"method_types": method_types, "rows": rows, "column_totals": column_totals, "grand_total": grand_total}


def build_method_pie(method_type: str | None = None) -> list[dict]:
    """
    Pie chart data: ACCU surrenders sliced by methodology sub-label.
    Returns list of dicts [{name, value}] sorted descending.
    """
    df = load_surrender_methods()
    if method_type:
        df = df[df["method_type"] == method_type]
    result = (
        df.groupby("method_type")["quantity"]
        .sum()
        .reset_index()
        .rename(columns={"method_type": "name", "quantity": "value"})
        .sort_values("value", ascending=False)
        .to_dict("records")
    )
    return [{"name": r["name"], "value": int(r["value"])} for r in result]


# ── Credit / Issuance analytics ────────────────────────────────────────────────


def build_credit_kpis() -> dict:
    """
    Returns dict with keys:
      total_accus_issued_all_time, latest_quarter_issuance, latest_quarter_label,
      total_holdings_latest, smc_holdings_latest,
      projects_with_credits, total_projects
    """
    proj = load_project_register()
    qcmr = load_qcmr()

    issuance = qcmr["issuance"]
    latest_q = issuance.dropna(subset=["Total"]).iloc[-1]
    q_label = f"{latest_q['Quarter']} {latest_q['Year']}"

    holdings = qcmr["holdings"]
    latest_h = holdings.dropna(subset=["Total holdings"]).iloc[-1]

    smc = qcmr["smc_holdings"]
    latest_smc = smc.dropna(subset=["Total holdings"]).iloc[-1]

    active = proj[~proj["revoked"]]

    return {
        "total_accus_issued_all_time": int(proj["accus_issued"].sum()),
        "latest_quarter_issuance": int(latest_q["Total"]),
        "latest_quarter_label": q_label,
        "total_holdings_latest": int(latest_h["Total holdings"]),
        "smc_holdings_latest": int(latest_smc["Total holdings"]),
        "projects_with_credits": int((active["accus_issued"] > 0).sum()),
        "total_projects": len(active),
    }


def build_annual_issuance_by_fy() -> pd.DataFrame:
    """
    Annual ACCU issuance by method type, sourced directly from the project register FY columns.
    Returns DataFrame with columns: year (FY start), fy_label, vegetation, waste,
      savanna_fire, energy_efficiency, industrial_fugitives, agriculture,
      carbon_capture, transport, facilities, total
    """
    df = load_project_register()
    fy_cols = [c for c in df.columns if c.startswith("fy_") and c[3:].isdigit()]
    method_keys = list(_METHOD_KEY.values())

    rows = []
    for fy_col in sorted(fy_cols, key=lambda c: int(c[3:])):
        start_year = int(fy_col[3:])
        row: dict = {"year": start_year, "fy_label": _fy_label(start_year)}
        for key in set(method_keys):
            row[key] = 0
        # sum per method type
        for mt, key in _METHOD_KEY.items():
            mask = df["method_type"].str.lower() == mt
            row[key] = row.get(key, 0) + int(df.loc[mask, fy_col].sum())
        row["total"] = sum(row[k] for k in set(method_keys))
        rows.append(row)

    result = pd.DataFrame(rows)
    # Drop years with zero total (no data yet)
    result = result[result["total"] > 0].reset_index(drop=True)
    return result


def build_quarterly_issuance(quarters_back: int = 12) -> pd.DataFrame:
    """
    Last N quarters of ACCU issuance from QCMR, by method.
    Returns DataFrame with columns: year, quarter, label, vegetation, waste, … , total
    """
    qcmr = load_qcmr()
    df = qcmr["issuance"].dropna(subset=["Total"]).copy()
    df = df.tail(quarters_back).reset_index(drop=True)
    df["label"] = df["Quarter"].astype(str) + " " + df["Year"].astype(str)
    rename = {
        "Vegetation": "vegetation",
        "Waste": "waste",
        "Savanna fire management": "savanna_fire",
        "Energy efficiency": "energy_efficiency",
        "Industrial fugitives": "industrial_fugitives",
        "Agriculture": "agriculture",
        "Carbon Capture": "carbon_capture",
        "Transport": "transport",
        "Facilities": "facilities",
        "Total": "total",
    }
    df = df.rename(columns=rename)
    keep = ["Year", "Quarter", "label"] + [v for v in rename.values() if v in df.columns]
    return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


def build_projects_issuing_by_fy(filters: dict | None = None) -> pd.DataFrame:
    """
    Count of projects issuing credits per financial year, split into first-year vs ongoing.
    Returns DataFrame with columns: fy_label, fy_start, first_year, ongoing, total
    """
    df = load_project_register()
    if filters:
        if filters.get("method_type"):
            df = df[df["method_type"] == filters["method_type"]]
        if filters.get("lead"):
            df = df[df["proponent"] == filters["lead"]]

    df = df[~df["revoked"]].copy()
    fy_cols = sorted(
        [c for c in df.columns if c.startswith("fy_") and c[3:].isdigit()],
        key=lambda c: int(c[3:]),
    )

    rows = []
    for fy_col in fy_cols:
        start_year = int(fy_col[3:])
        issuing = df[df[fy_col] > 0]
        if issuing.empty:
            continue
        # First year = projects whose first non-zero FY is this one
        earlier_cols = [c for c in fy_cols if int(c[3:]) < start_year]
        if earlier_cols:
            first_year = int((issuing[earlier_cols].sum(axis=1) == 0).sum())
        else:
            first_year = len(issuing)
        ongoing = len(issuing) - first_year
        rows.append({
            "fy_label": _fy_label(start_year),
            "fy_start": start_year,
            "first_year": first_year,
            "ongoing": ongoing,
            "total": len(issuing),
        })

    return pd.DataFrame(rows)


# ── Project registration analytics ────────────────────────────────────────────


def build_project_kpis(filters: dict | None = None) -> dict:
    """
    Returns dict with keys:
      total_projects, new_projects_last_month, revoked_projects,
      project_leads, methods, active_methods, projects_with_credits,
      pct_with_credits, latest_registration
    """
    df = load_project_register()
    if filters:
        if filters.get("method_type"):
            df = df[df["method_type"] == filters["method_type"]]
        if filters.get("lead"):
            df = df[df["proponent"] == filters["lead"]]

    active = df[~df["revoked"]]
    latest_ym = active["registered_ym"].dropna().max()

    return {
        "total_projects": len(active),
        "new_projects_last_month": int(
            (active["registered_ym"] == latest_ym).sum()
        ),
        "revoked_projects": int(df["revoked"].sum()),
        "project_leads": active["proponent"].nunique(),
        "methods": df["method"].nunique(),
        "active_methods": active["method"].nunique(),
        "projects_with_credits": int((active["accus_issued"] > 0).sum()),
        "pct_with_credits": float(
            (active["accus_issued"] > 0).sum() / len(active) * 100
        ) if len(active) else 0.0,
        "latest_registration": latest_ym,
    }


def build_projects_by_year(filters: dict | None = None) -> pd.DataFrame:
    """
    Active project registrations grouped by calendar year, with per-method breakdown.
    Returns DataFrame with columns: year, total, vegetation, waste, savanna_fire, …
    """
    df = load_project_register()
    if filters:
        if filters.get("method_type"):
            df = df[df["method_type"] == filters["method_type"]]
        if filters.get("lead"):
            df = df[df["proponent"] == filters["lead"]]

    df = df[~df["revoked"] & df["registered_date"].notna()].copy()
    df["year"] = df["registered_date"].dt.year

    pivot = (
        df.groupby(["year", "method_type"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    pivot["total"] = pivot.drop(columns="year").sum(axis=1)
    return pivot.sort_values("year").reset_index(drop=True)


def build_projects_per_lead(top_n: int = 10, filters: dict | None = None) -> pd.DataFrame:
    """
    Top N proponents by active project count.
    Returns DataFrame with columns: lead, total, (one column per method type)
    """
    df = load_project_register()
    if filters and filters.get("method_type"):
        df = df[df["method_type"] == filters["method_type"]]

    df = df[~df["revoked"]].copy()
    pivot = (
        df.groupby(["proponent", "method_type"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    pivot["total"] = pivot.drop(columns="proponent").sum(axis=1)
    pivot = pivot.sort_values("total", ascending=False).head(top_n)
    pivot = pivot.rename(columns={"proponent": "lead"})
    return pivot.reset_index(drop=True)


def build_lead_momentum(top_n: int = 8, filters: dict | None = None) -> pd.DataFrame:
    """
    Cumulative project counts over time for the top N proponents.
    Returns DataFrame with columns: year_month, label, <lead_name>, …
    One row per calendar month from earliest to latest registration.
    """
    df = load_project_register()
    if filters and filters.get("method_type"):
        df = df[df["method_type"] == filters["method_type"]]

    active = df[~df["revoked"] & df["registered_date"].notna()].copy()

    # Identify top N leads
    top_leads = (
        active.groupby("proponent").size().sort_values(ascending=False).head(top_n).index.tolist()
    )
    active = active[active["proponent"].isin(top_leads)].copy()

    # Build full month range
    min_ym = active["registered_ym"].min()
    max_ym = active["registered_ym"].max()
    months = pd.date_range(min_ym, max_ym, freq="MS").strftime("%Y-%m").tolist()

    # Cumulative count per lead per month
    monthly = (
        active.groupby(["registered_ym", "proponent"])
        .size()
        .unstack(fill_value=0)
        .reindex(months, fill_value=0)
        .cumsum()
    )
    monthly.index.name = "year_month"
    monthly = monthly.reset_index()
    monthly["label"] = pd.to_datetime(monthly["year_month"]).dt.strftime("%b %Y")

    cols = ["year_month", "label"] + top_leads
    return monthly[[c for c in cols if c in monthly.columns]].reset_index(drop=True)


# ── Retirement / cancellation analytics ───────────────────────────────────────


def build_retirement_kpis() -> dict:
    """
    Returns dict with keys:
      units_cancelled_last_month, units_cancelled_mom_change,
      voluntary_entities_last_month, voluntary_surrenders_last_month,
      credits_held_latest_quarter, credit_annual_retirements_latest_year,
      latest_month_label, latest_quarter_label
    """
    canc = load_voluntary_cancellations()
    qcmr = load_qcmr()

    # Find latest "complete" month (>= 5 transactions)
    monthly = canc.groupby("year_month").agg(
        units=("units", "sum"),
        transactions=("units", "count"),
        entities=("entity", "nunique"),
    ).reset_index().sort_values("year_month")
    complete = monthly[monthly["transactions"] >= 5]

    if complete.empty:
        latest_row = monthly.iloc[-1] if not monthly.empty else None
        prev_row = None
    else:
        latest_row = complete.iloc[-1]
        prev_row = complete.iloc[-2] if len(complete) >= 2 else None

    latest_label = (
        pd.to_datetime(latest_row["year_month"]).strftime("%b %Y")
        if latest_row is not None
        else "—"
    )

    # Latest holdings quarter
    holdings = qcmr["holdings"].dropna(subset=["Total holdings"])
    latest_h = holdings.iloc[-1] if not holdings.empty else None
    q_label = (
        f"{latest_h['Quarter']} {latest_h['Year']}" if latest_h is not None else "—"
    )

    # Latest complete year annual retirements (from QCMR cancellations)
    ann = qcmr["cancellations"].dropna(subset=["Annual total"])
    latest_ann = ann.iloc[-1] if not ann.empty else None

    return {
        "units_cancelled_last_month": int(latest_row["units"]) if latest_row is not None else 0,
        "units_cancelled_mom_change": (
            int(latest_row["units"] - prev_row["units"]) if prev_row is not None else None
        ),
        "voluntary_entities_last_month": int(latest_row["entities"]) if latest_row is not None else 0,
        "voluntary_surrenders_last_month": int(latest_row["transactions"]) if latest_row is not None else 0,
        "credits_held_latest_quarter": int(latest_h["Total holdings"]) if latest_h is not None else 0,
        "credit_annual_retirements_latest_year": (
            int(latest_ann["Annual total"]) if latest_ann is not None else 0
        ),
        "latest_month_label": latest_label,
        "latest_quarter_label": q_label,
    }


def build_monthly_cancellations() -> pd.DataFrame:
    """
    Monthly voluntary ACCU cancellations.
    Returns DataFrame with columns: year_month, label, units
    """
    df = load_voluntary_cancellations()
    monthly = (
        df.groupby("year_month")["units"]
        .sum()
        .reset_index()
        .sort_values("year_month")
    )
    monthly["label"] = pd.to_datetime(monthly["year_month"]).dt.strftime("%b %Y")
    return monthly.reset_index(drop=True)


def build_top_cancelling_entities(months_back: int = 12, top_n: int = 10) -> pd.DataFrame:
    """
    Top N entities by voluntary cancellation volume over the last N months.
    Returns DataFrame with columns: entity, units, first_date, latest_date
    """
    df = load_voluntary_cancellations()
    latest_ym = df["year_month"].max()
    cutoff = (
        pd.to_datetime(latest_ym) - pd.DateOffset(months=months_back - 1)
    ).strftime("%Y-%m")
    df = df[df["year_month"] >= cutoff]
    result = (
        df.groupby("entity")
        .agg(units=("units", "sum"), first_date=("date", "min"), latest_date=("date", "max"))
        .reset_index()
        .sort_values("units", ascending=False)
        .head(top_n)
    )
    return result.reset_index(drop=True)


def build_annual_retirements() -> pd.DataFrame:
    """
    Annual ACCU retirements: voluntary, compliance, government, safeguard surrenders.
    Returns DataFrame with columns: year, voluntary, compliance, government, safeguard, total
    """
    qcmr = load_qcmr()

    # Aggregate QCMR cancellations by year
    canc = qcmr["cancellations"].copy()
    by_year = (
        canc.groupby("Year")
        .agg(
            voluntary=("Voluntary cancellations", "sum"),
            compliance=("Compliance cancellations", "sum"),
            government=("Government cancellations", "sum"),
        )
        .reset_index()
        .rename(columns={"Year": "year"})
    )

    # Safeguard surrenders from QCMR figure-1-6
    saf = qcmr["safeguard_surrenders"].copy()
    saf_year = (
        saf.groupby("Year")
        .agg(safeguard=("ACCUs surrendered", "sum"))
        .reset_index()
        .rename(columns={"Year": "year"})
    )

    merged = by_year.merge(saf_year, on="year", how="outer").fillna(0)
    merged["total"] = merged[["voluntary", "compliance", "government", "safeguard"]].sum(axis=1)
    return merged.sort_values("year").reset_index(drop=True)


def build_holdings_timeseries() -> pd.DataFrame:
    """
    ACCU and SMC holdings by entity type per quarter.
    Returns DataFrame with columns:
      year, quarter, label, proponent, intermediary, safeguard,
      government, business, smc, total_holdings
    """
    qcmr = load_qcmr()
    h = qcmr["holdings"].copy()
    smc = qcmr["smc_holdings"].copy()

    h["label"] = h["Quarter"].astype(str) + " " + h["Year"].astype(str)
    h["yq"] = h["Year"].astype(str) + "-" + h["Quarter"].astype(str)

    smc["yq"] = smc["Year"].astype(str) + "-" + smc["Quarter"].astype(str)
    smc_map = smc.set_index("yq")["Total holdings"].to_dict()

    h = h.rename(columns={
        "ACCU project proponent": "proponent",
        "Intermediary": "intermediary",
        "Safeguard": "safeguard",
        "Government": "government",
        "Business": "business",
        "Total holdings": "total_holdings",
    })
    h["smc"] = h["yq"].map(smc_map).fillna(0)

    keep = ["Year", "Quarter", "label", "proponent", "intermediary",
            "safeguard", "government", "business", "smc", "total_holdings"]
    return h[[c for c in keep if c in h.columns]].reset_index(drop=True)
