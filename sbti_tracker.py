"""Corporate Climate Strategy BD Tracker — target screen, delivery, TPI-style indicators.

Run: streamlit run sbti_tracker.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    debug_extract,
    fetch_and_parse,
    fetch_pdf,
    load_stored_urls,
    lookup_stored_url,
    parse_emissions,
    search_report_url,
)
from modules.nger import (
    find_committed_nger,
    infer_year_from_filename,
    inject_to_cache as nger_inject_to_cache,
    load_nger,
)
from modules.tpi import MQ_COLOUR, CP_COLOUR, attach_tpi
from modules.bd_insights import INSIGHTS
from modules.asrs import (
    add_asrs_columns,
    GROUP_URGENCY_NOTE,
    bd_priority_label,
)
from modules.company_brief import build_brief
from modules.voluntary import voluntary_retirements, is_available as voluntary_available
from modules.safeguard import aggregate as safeguard_aggregate, is_available as safeguard_available
from modules.nzt import load_nzt, overlay_nzt, NZT_COLS


def _column_config():
    """Centralised column display rules: friendly names + integer year format."""
    yr = st.column_config.NumberColumn(format="%d")
    return {
        "Cohort": st.column_config.TextColumn(
            "Companies",
            help="Which group the company sits in: ASX listed (SBTi), Australian "
                 "Corporate / FI (SBTi private), ASX 200 — no SBTi target, or "
                 "NGER reporters (not in cohort).",
        ),
        "Near-term Status": st.column_config.TextColumn(
            "SBTi Status",
            help="Status of the SBTi target: Targets set (validated near-term), "
                 "Committed (intent letter only), Commitment removed, "
                 "or blank if not in SBTi.",
        ),
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
    page_title="Corporate Climate Strategy BD Tracker",
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

/* Big, identifiable top-level tab bar */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: #F1F5F9;
    padding: 8px;
    border-radius: 12px;
    margin-bottom: 18px;
    border: 1px solid #E2E8F0;
}
.stTabs [data-baseweb="tab"] {
    height: 56px;
    padding: 0 22px;
    font-size: 1.05rem;
    font-weight: 600;
    color: #334155;
    background: #FFFFFF;
    border-radius: 8px;
    border: 1px solid #E2E8F0;
    transition: all 0.15s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    background: #EFF6FF;
    color: #1E40AF;
    border-color: #BFDBFE;
}
.stTabs [aria-selected="true"] {
    background: #1E40AF !important;
    color: #FFFFFF !important;
    border-color: #1E40AF !important;
    box-shadow: 0 2px 6px rgba(30, 64, 175, 0.25);
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-border"]    { display: none; }
</style>
""",
    unsafe_allow_html=True,
)


# ─── Sidebar: data load ────────────────────────────────────────────────────────
st.sidebar.title("🇦🇺 Corporate Climate Strategy BD Tracker")
st.sidebar.caption("Target adequacy, V2 reset risk, delivery progress")

with st.sidebar.expander("📁 Data sources", expanded=False):
    sbti_upload = st.file_uploader(
        "SBTi Companies-Taking-Action (CSV/XLSX)",
        type=["csv", "xlsx", "xls"],
        help="Override the bundled SBTi data with a fresh download.",
    )
    st.markdown("---")
    st.markdown("**🌍 Net Zero Tracker**")
    st.caption(
        "Upload the [Net Zero Tracker](https://zerotracker.net/) snapshot XLSX "
        "to enrich AUS Company Profile with targets for non-SBTi companies."
    )
    nzt_upload = st.file_uploader(
        "NZT current_snapshot (XLSX)",
        type=["xlsx", "xls"],
        key="nzt_upload",
        help="Download from zerotracker.net → Data → Current snapshot.",
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
    st.title("🇦🇺 Corporate Climate Strategy BD Tracker")
    st.warning(
        f"No SBTi data loaded. Upload the **Companies Taking Action** dataset from "
        f"the sidebar, or commit it to `{DATA_DIR / 'sbti_companies.xlsx'}`."
    )
    st.stop()

screen = build_all(sbti_df)

emissions_cache = load_cache()


@st.cache_data(show_spinner=False)
def _load_nzt(file_bytes: bytes | None, name: str | None) -> pd.DataFrame:
    if file_bytes is None:
        return pd.DataFrame()
    buf = io.BytesIO(file_bytes)
    buf.name = name or "nzt.xlsx"
    return load_nzt(buf)


nzt_df = _load_nzt(
    nzt_upload.getvalue() if nzt_upload else None,
    nzt_upload.name if nzt_upload else None,
)

if not nzt_df.empty:
    st.sidebar.caption(f"✅ NZT loaded — {len(nzt_df)} Australian companies")
elif nzt_upload:
    st.sidebar.warning("⚠️ NZT file loaded but no Australian companies found. Check Country = 'AUS' and Entity_type = 'Company'.")


# Auto-import a committed NGER spreadsheet if present and not already imported
@st.cache_data(show_spinner="Importing committed NGER data…")
def _auto_import_nger(nger_path_str: str, mtime: float, cohort_names_tuple: tuple, isin_pairs: tuple):
    """Cached wrapper — keys on path + mtime so we don't re-import on every rerun."""
    p = Path(nger_path_str)
    nger_df = load_nger(p)
    year = infer_year_from_filename(p) or 2025
    isin_lookup = dict(isin_pairs)
    return nger_df, year, isin_lookup


_committed_nger = find_committed_nger()
if _committed_nger is not None:
    try:
        nger_df, _yr, _isin_lookup = _auto_import_nger(
            str(_committed_nger),
            _committed_nger.stat().st_mtime,
            tuple(screen[CANON["company"]].dropna().astype(str)),
            tuple(zip(screen[CANON["company"]].astype(str),
                      screen.get(CANON["isin"], pd.Series([""] * len(screen))).astype(str))),
        )
        already_imported = any(
            any(h.get("source") == "nger" and h.get("year") == _yr for h in rec.get("history", []))
            for rec in emissions_cache.values()
        )
        if not already_imported:
            cohort_names = list(screen[CANON["company"]].dropna().unique())
            nger_inject_to_cache(nger_df, cohort_names, emissions_cache, _yr, _isin_lookup)
            save_cache(emissions_cache)
    except Exception as exc:
        st.sidebar.warning(f"NGER auto-import skipped: {exc}")

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

    st.markdown("---")
    st.markdown("**📚 Bulk PDF upload**")
    st.caption(
        "Drop up to 10 sustainability-report PDFs. Each one is parsed for "
        "Scope 1/2/3 + reporting year, then matched to a cohort company by "
        "filename or auto-detection. Review the results table before saving."
    )
    bulk_pdfs = st.file_uploader(
        "PDFs (multiple)",
        type=["pdf"],
        accept_multiple_files=True,
        key="bulk_pdf_upload",
        help="Name files after the company (e.g. 'BHP_FY24.pdf') for auto-matching.",
    )
    if bulk_pdfs:
        from modules.researched import _name_key as _nk
        cohort_names = list(screen[CANON["company"]].dropna().unique())
        cohort_key_map = {_nk(n): n for n in cohort_names}

        st.markdown(f"**{len(bulk_pdfs)} PDF(s) ready to parse:**")
        results = []
        prog = st.progress(0.0)
        for i, f in enumerate(bulk_pdfs, start=1):
            prog.progress(i / len(bulk_pdfs), text=f"{i}/{len(bulk_pdfs)} {f.name}")
            try:
                parsed = parse_emissions(f.getvalue())
            except Exception as exc:
                results.append({"File": f.name, "Match": "ERROR", "Year": "",
                    "S1": "", "S2": "", "S3": "", "Error": str(exc)[:60]})
                continue
            stem = f.name.rsplit(".", 1)[0]
            stem_key = _nk(stem)
            best_match = None
            for k, n in cohort_key_map.items():
                if not k or not stem_key:
                    continue
                if k == stem_key or k in stem_key or stem_key in k:
                    best_match = n
                    break
            results.append({
                "File": f.name,
                "Match": best_match or "— pick below —",
                "Year": parsed.get("reporting_year") or "",
                "S1": parsed.get("s1") or "",
                "S2": parsed.get("s2") or "",
                "S3": parsed.get("s3") or "",
            })
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

        if st.button("💾 Save all matched rows to emissions cache", key="bulk_save"):
            saved = 0
            for f, r in zip(bulk_pdfs, results):
                if r.get("Match", "").startswith("—") or not r.get("Year"):
                    continue
                try:
                    yr = int(r["Year"])
                except (TypeError, ValueError):
                    continue
                key = r["Match"]
                rec = emissions_cache.get(key, {"company": key, "isin": "", "history": []})
                rec["history"] = [h for h in rec["history"] if h.get("year") != yr]
                rec["history"].append({
                    "year": yr,
                    "s1": float(r["S1"]) if r.get("S1") else None,
                    "s2": float(r["S2"]) if r.get("S2") else None,
                    "s3": float(r["S3"]) if r.get("S3") else None,
                    "source": "bulk-pdf-upload",
                    "source_url": f.name,
                })
                emissions_cache[key] = rec
                saved += 1
            save_cache(emissions_cache)
            st.success(f"Saved {saved} of {len(bulk_pdfs)} to emissions cache. "
                       "Reload page to refresh the cohort table.")

    st.markdown("---")
    st.markdown("**🇦🇺 NGER bulk import**")
    st.caption(
        "Upload the **Corporate emissions and energy data** spreadsheet from "
        "[cer.gov.au](https://cer.gov.au/markets/reports-and-data/nger-reporting-data-and-registers/). "
        "Every Aussie company emitting >50 ktCO2e is in there — the gold-standard "
        "Scope 1 + 2 source for the entire cohort. Released annually around February."
    )
    nger_file = st.file_uploader(
        "NGER spreadsheet (.xlsx / .xls)",
        type=["xlsx", "xls"],
        key="nger_upload",
    )
    nger_year = st.number_input(
        "Reporting year (FY end)",
        min_value=2010, max_value=2035, value=2025, step=1,
        key="nger_year",
        help="2025 = FY July 2024–June 2025 (the most recent NGER dataset).",
    )
    if nger_file is not None and st.button("Import NGER → emissions cache", key="nger_import"):
        try:
            nger_df = load_nger(nger_file.getvalue())
            cohort_names = list(screen[CANON["company"]].dropna().unique())
            isin_lookup = dict(zip(screen[CANON["company"]], screen.get(CANON["isin"], "")))
            ingested, unmatched = nger_inject_to_cache(
                nger_df, cohort_names, emissions_cache,
                int(nger_year), isin_lookup,
            )
            save_cache(emissions_cache)
            st.success(
                f"NGER ingest complete: {ingested} cohort companies matched and updated "
                f"({len(nger_df)} reporters in NGER file)."
            )
            if unmatched:
                with st.expander(f"⚠️ Unmatched cohort companies ({len(unmatched)})"):
                    for c in unmatched[:50]:
                        st.write(f"• {c}")
                    if len(unmatched) > 50:
                        st.caption(f"... and {len(unmatched) - 50} more")
        except Exception as exc:
            st.error(f"NGER import failed: {exc}")

    st.markdown("---")
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
    n_sbti = sum(1 for r in stored_urls if r.get("source") == "sbti")
    n_asx200 = sum(1 for r in stored_urls if r.get("source") == "asx200")
    with st.sidebar.expander(
        f"🌐 Stored report URLs ({len(stored_urls)})", expanded=False
    ):
        st.caption(
            f"**{n_sbti}** SBTi cohort + **{n_asx200}** non-SBTi cohort URLs. "
            "Click 'Fetch all' to download + parse each report. Runs on this "
            "server's network — Streamlit Cloud reaches most corporate sites; "
            "this dev sandbox does not."
        )
        scope = st.radio(
            "Which to fetch",
            ["All", "SBTi cohort only", "Non-SBTi cohort only"],
            index=0, horizontal=True,
        )
        if st.button("⚡ Fetch + parse all stored reports"):
            target = stored_urls
            if scope == "SBTi cohort only":
                target = [r for r in stored_urls if r.get("source") == "sbti"]
            elif scope == "Non-SBTi cohort only":
                target = [r for r in stored_urls if r.get("source") == "asx200"]
            progress = st.progress(0.0)
            log_box = st.empty()
            successes, failures = [], []
            n = len(target)
            for i, rec in enumerate(target, start=1):
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
            log_box.success(
                f"Fetched: {len(successes)} / {n}. "
                f"Now click 💾 Download emissions cache (above) and send the "
                f"file to Claude — Claude commits it so the data persists for the team."
            )
            if failures:
                with log_box.container():
                    st.error(f"Failed: {len(failures)}")
                    for c, e in failures:
                        st.caption(f"• {c}: {e}")

screen = build_delivery(screen, emissions_cache)
screen = attach_tpi(screen)


# ─── Title + top-level tabs ───────────────────────────────────────────────────
st.title(f"🇦🇺 Corporate Climate Strategy BD Tracker")
st.caption(
    "All Australian-listed and large private SBTi companies, plus ASX 200 companies "
    "without SBTi targets. Pick a tab to explore."
)

tab_company, tab_asrs, tab_safeguard, tab_insights, tab_brief, tab_rulebook, tab_methodology, tab_philippines, tab_malaysia = st.tabs(
    ["🔍 Company drill-down", "🏢 AUS Company Profile", "🏭 Safeguard Register", "💡 BD Insights", "📋 Company Brief", "📚 Sector rulebook", "📖 Methodology", "🇵🇭 Philippines", "🇲🇾 Malaysia"]
)

# ─── Sidebar filter setup ─────────────────────────────────────────────────────
sectors = sorted([s for s in screen[CANON["sector"]].dropna().unique() if str(s).strip()])
listed_options = ["ASX Listed", "Private & Unlisted"]
sbti_options = ["Yes", "No"]
nger_options = ["Yes", "No"]
asrs_tiers_present = [t for t in ["Tier 1", "Tier 1 (proxy)", "Tier 2", "Tier 2 (proxy)", "Tier 3", "Unclassified"]
                      if t in screen.get("ASRS Tier", pd.Series(dtype=str)).unique()]

with st.sidebar.expander("🔍 Filters", expanded=False):
    st.caption("**Filters** — change any to narrow the view; defaults show all companies.")
    f_listed = st.multiselect(
        "Listed",
        listed_options,
        default=[],
        key="ftr_listed",
        help="ASX Listed = traded on the ASX. Private & Unlisted = private companies and NGER reporters.",
    )
    f_sbti = st.multiselect(
        "SBTi target",
        sbti_options,
        default=[],
        key="ftr_sbti",
        help="Yes = company has an SBTi entry (validated, committed, or removed).\nNo = no SBTi engagement.",
    )
    f_nger = st.multiselect(
        "NGER reporter",
        nger_options,
        default=[],
        key="ftr_nger",
        help="Yes = company reports under the National Greenhouse and Energy Reporting Act, or is covered under the Safeguard Mechanism (100kt threshold implies NGER obligation).",
    )
    f_tier = st.multiselect(
        "ASRS reporting tier",
        asrs_tiers_present,
        default=[],
        key="ftr_tier",
        help=(
            "AASB S2 Climate-related Disclosures reporting tier.\n\n"
            "**Tier 1**: ≥2 of A$500M revenue / A$1B assets / 500 employees.\n"
            "**Tier 2**: ≥2 of A$200M / A$500M / 500 employees.\n"
            "**Tier 3**: ≥2 of A$50M / A$25M / 100 employees.\n\n"
            "**(proxy)** = financial data not on file; tier estimated from market cap."
        ),
    )
    search = st.text_input("🔍 Search by company name", key="ftr_search")
    if st.button("↻ Clear filters", use_container_width=True):
        for k in ("ftr_search", "ftr_sector", "ftr_priority", "ftr_yrs",
                  "ftr_mq", "ftr_cp", "ftr_delivery", "ftr_listed", "ftr_tier",
                  "ftr_sbti", "ftr_nger"):
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()
    with st.expander("More filters", expanded=False):
        f_sector = st.multiselect("Sector", sectors, key="ftr_sector")
        f_priority = st.radio(
            "Outreach priority",
            ["All", "High (target ≤2030 or scope gap)", "Low (target >2030 and on track)"],
            index=0, key="ftr_priority",
            help="High = target year ≤2030, target year passed, or required scopes missing.",
        )
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
        f_cp = st.multiselect(
            "CP Alignment",
            ["Aligned 1.5°C", "Aligned Below 2°C", "Aligned 2°C / NDC",
             "Not aligned", "Insufficient disclosure"],
            key="ftr_cp",
        )
        f_delivery = st.multiselect(
            "Delivery RAG",
            ["Green", "Amber", "Red", "N/A"],
            key="ftr_delivery",
        )

# Track active filters for chip display
active_filters: list[str] = []

filtered = screen.copy()
total_in_cohort = len(filtered)

if f_listed:
    filtered = filtered[filtered["Listed"].isin(f_listed)]
    active_filters.append(f"Listed: {', '.join(f_listed)}")
if f_sbti:
    filtered = filtered[filtered["SBTi"].isin(f_sbti)]
    active_filters.append(f"SBTi: {', '.join(f_sbti)}")
if f_nger:
    if "Yes" in f_nger and "No" not in f_nger:
        filtered = filtered[filtered["NGER Reporter"].str.startswith("Yes")]
        active_filters.append("NGER: Yes")
    elif "No" in f_nger and "Yes" not in f_nger:
        filtered = filtered[filtered["NGER Reporter"] == "No"]
        active_filters.append("NGER: No")
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

        # ── Safeguard Mechanism ──
        st.markdown("---")
        st.markdown("### Safeguard Mechanism")
        from modules.safeguard import aggregate as _sfg_agg, is_available as _sfg_avail
        if not _sfg_avail():
            st.caption(
                "Safeguard data not loaded. Copy `baselines-and-emissions.csv` from the "
                "CER Safeguard register into `data/safeguard_baselines.csv` to enable this section."
            )
        else:
            sfg = _sfg_agg(company)
            if sfg is None:
                st.info(
                    f"**{company}** is not covered under the Safeguard Mechanism — "
                    "either below the 100 kt CO₂e threshold or no matching facilities found."
                )
            else:
                fac_count = sfg["facility_count"]
                sfg_c1, sfg_c2, sfg_c3, sfg_c4 = st.columns(4)
                sfg_c1.metric(
                    f"Facilit{'y' if fac_count == 1 else 'ies'}",
                    fac_count,
                )

                def _kt(v):
                    if v is None or (isinstance(v, float) and pd.isna(v)):
                        return "—"
                    v = float(v)
                    if abs(v) >= 1_000_000:
                        return f"{v/1_000_000:.2f} Mt"
                    if abs(v) >= 1_000:
                        return f"{v/1_000:.1f} kt"
                    return f"{v:.0f} t"

                sfg_c2.metric("Covered emissions", _kt(sfg["covered_tco2e"]))
                sfg_c3.metric("Baseline", _kt(sfg["baseline_tco2e"]))
                net = sfg["net_position_tco2e"]
                sfg_c4.metric(
                    "Net position",
                    _kt(net),
                    delta="Below baseline" if net >= 0 else "Above baseline (shortfall)",
                    delta_color="normal" if net >= 0 else "inverse",
                )

                accu = sfg["accus_surrendered_tco2e"]
                smc = sfg["smcs_surrendered_tco2e"]
                total_sur = sfg["total_surrendered_tco2e"]
                if total_sur and total_sur > 0:
                    st.caption(
                        f"Surrendered: {_kt(accu)} ACCUs + {_kt(smc)} SMCs = **{_kt(total_sur)}** total"
                    )

                facs = sfg["facilities"]
                if not facs.empty:
                    disp_cols = [c for c in ["facility_name", "state", "baseline",
                                              "covered_emissions", "total_surrendered", "net_position"]
                                 if c in facs.columns]
                    facs_disp = facs[disp_cols].copy()
                    facs_disp.columns = [c.replace("_", " ").title() for c in disp_cols]
                    st.dataframe(facs_disp, use_container_width=True, hide_index=True)

                st.caption("Source: CER Safeguard Mechanism register. Net position: positive = below baseline (compliant).")

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
                # If parser got nothing useful, show debug dump so user can diagnose
                if parsed_seed and parsed_seed.get("s1") is None and parsed_seed.get("s2") is None:
                    with st.expander("🔍 Nothing found — show raw PDF extraction (debug)", expanded=True):
                        st.caption(
                            "The parser couldn't find Scope 1/2/3 values. "
                            "Check below to see what pdfplumber extracted. "
                            "Common causes: image-based PDF (scanned), non-standard "
                            "table layout, or numbers reported in Mt not t."
                        )
                        with st.spinner("Extracting debug info…"):
                            dbg = debug_extract(pdf_up.getvalue(), max_pages=15)
                        if dbg.get("error"):
                            st.error(dbg["error"])
                        else:
                            st.info(
                                f"{dbg['total_pages']} pages total — showing first 15. "
                                f"Total text chars extracted: {dbg['text_chars']:,}. "
                                + ("⚠️ Very low char count — likely a scanned/image PDF. "
                                   "You'll need to enter emissions manually below."
                                   if dbg['text_chars'] < 500 else
                                   "Text found — the layout may be non-standard. "
                                   "Check the table dumps below.")
                            )
                            for p in dbg["pages"][:8]:
                                with st.expander(f"Page {p['page']}", expanded=False):
                                    if p["text"].strip():
                                        st.text(p["text"][:1500])
                                    for ti, tbl in enumerate(p["tables"][:2]):
                                        st.caption(f"Table {ti+1}")
                                        try:
                                            st.dataframe(pd.DataFrame(tbl), hide_index=True)
                                        except Exception:
                                            st.text(str(tbl)[:400])

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
                with st.expander("Show source snippets (where each number came from)"):
                    for k, snip in parsed_seed["snippets"].items():
                        st.code(f"{k}: {snip}", language=None)
            ec = parsed_seed.get("emissions_candidates") or []
            if ec:
                with st.expander(
                    f"All {len(ec)} emissions candidates found in PDF tables "
                    "(use to verify the auto-pick, or pick a different year)"
                ):
                    st.caption(
                        "Latest year is auto-picked. If the wrong number was chosen "
                        "(e.g. base year instead of current), copy the right value "
                        "into the form below."
                    )
                    ec_cols = [c for c in ["scope", "year", "value", "raw_value", "unit", "is_total", "row_text"] if c in pd.DataFrame(ec).columns]
                    cand_df = pd.DataFrame(ec)[ec_cols]
                    cand_df = cand_df.sort_values(
                        ["scope", "year"], ascending=[True, False], na_position="last"
                    )
                    st.dataframe(cand_df, use_container_width=True, height=300, hide_index=True)
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


with tab_insights:
    st.markdown("### BD Insights — pre-canned strategic cuts")
    st.caption(
        "Hand-curated views on where Pollination's advisory wedge is widest. "
        "Each insight applies to the **full cohort** (top filters above don't change these)."
    )
    insight_choice = st.selectbox(
        "Pick an insight",
        list(INSIGHTS.keys()),
        key="bd_insight_pick",
    )
    insight_fn = INSIGHTS[insight_choice]
    try:
        out = insight_fn(screen)
    except Exception as exc:
        st.error(f"Insight failed: {exc}")
        out = None
    if out:
        st.markdown(f"#### {out['title']}")
        st.info(out["summary"])
        tbl = out.get("table")
        if tbl is not None and not tbl.empty:
            st.dataframe(
                tbl, use_container_width=True, hide_index=True,
                column_config=_column_config(), height=520,
            )
            if out.get("table_caption"):
                st.caption(out["table_caption"])
            st.download_button(
                f"⬇ Download — {insight_choice} (CSV)",
                tbl.to_csv(index=False).encode("utf-8"),
                file_name=f"insight_{insight_choice.lower().replace(' ', '_')}.csv",
                mime="text/csv",
            )
        else:
            st.caption("(No rows matched this insight in the current cohort.)")


with tab_asrs:
    st.markdown("### 🏢 AUS Company Profile")
    st.caption(
        "Every cohort company mapped to its ASRS reporting group, SBTi/target status, "
        "near-term target wording, net-zero commitment, Safeguard Mechanism coverage, "
        "and voluntary ACCU retirements. Use this as your primary BD prospect list."
    )

    # ── Known FY year-end exceptions (ASX code → month-day string) ────────────
    _DEC_YE = {"RIO", "STO", "WDS", "WPL", "NHC", "WHC", "NUF", "KAR", "BPT"}
    _SEP_YE = {"ANZ", "NAB", "WBC", "BOQ", "BEN"}
    _MAR_YE = {"MQG"}

    def _fy_end(asx_code: str) -> str:
        c = str(asx_code).strip().upper()
        if c in _DEC_YE:
            return "31 Dec"
        if c in _SEP_YE:
            return "30 Sep"
        if c in _MAR_YE:
            return "31 Mar"
        return "30 Jun"

    def _first_asrs_report(asrs_group: str, fy_end: str) -> str:
        """First mandatory ASRS report period (financial year + approx due date)."""
        if asrs_group == "Group 1":
            if fy_end == "31 Dec":
                return "FY2025 (due ~Apr 2026)"
            if fy_end == "30 Sep":
                return "FY2025/26 (due ~Jan 2026)"
            if fy_end == "31 Mar":
                return "FY2025/26 (due ~Jul 2026)"
            return "FY2025/26 (due ~Oct 2026)"
        if asrs_group == "Group 2":
            if fy_end == "31 Dec":
                return "FY2026 (due ~Apr 2027)"
            return "FY2026/27 (due ~Oct 2027)"
        if asrs_group == "Group 3":
            if fy_end == "31 Dec":
                return "FY2027 (due ~Apr 2028)"
            return "FY2027/28 (due ~Oct 2028)"
        return "—"

    # ── Build enriched table (cached on company list hash) ────────────────────
    @st.cache_data(show_spinner="Building emissions & Safeguard view…", ttl=600)
    def _build_asrs_table(company_names: tuple, _screen_hash: int) -> pd.DataFrame:
        from modules.voluntary import voluntary_retirements as _vol
        from modules.safeguard import aggregate as _sfg

        rows = []
        for name in company_names:
            sfg = _sfg(name)
            vol = _vol(name)
            rows.append({
                "company": name,
                "sfg_surrendered": sfg["total_surrendered_tco2e"] if sfg else None,
                "vol_retirements": vol,
            })
        return pd.DataFrame(rows).set_index("company")

    _company_tuple = tuple(screen[CANON["company"]].dropna().astype(str).tolist())
    _screen_hash = hash(_company_tuple)
    enrich = _build_asrs_table(_company_tuple, _screen_hash)

    # ── Enrich screen with ASRS + CER columns ────────────────────────────────
    asrs_df = add_asrs_columns(screen).copy()
    asrs_df["FY Year End"] = asrs_df["ASX Code"].apply(
        lambda c: _fy_end(str(c)) if pd.notna(c) else "30 Jun"
    )
    asrs_df["First ASRS Report"] = asrs_df.apply(
        lambda r: _first_asrs_report(
            str(r.get("ASRS Group", "")),
            str(r.get("FY Year End", "30 Jun")),
        ),
        axis=1,
    )
    asrs_df["Safeguard Surrendered (tCO2e)"] = asrs_df[CANON["company"]].map(
        lambda n: enrich.loc[n, "sfg_surrendered"] if n in enrich.index else None
    )
    asrs_df["Voluntary Retirements (ACCUs)"] = asrs_df[CANON["company"]].map(
        lambda n: enrich.loc[n, "vol_retirements"] if n in enrich.index else None
    )

    # ── NZT overlay ───────────────────────────────────────────────────────────
    if not nzt_df.empty:
        asrs_df = overlay_nzt(asrs_df, nzt_df)

    target_col = next(
        (c for c in ("Target Classification", "Target Classification (BD)") if c in asrs_df.columns),
        None,
    )

    # ── KPI row ───────────────────────────────────────────────────────────────
    g1_all = asrs_df[asrs_df["ASRS Group"] == "Group 1"]
    g2_all = asrs_df[asrs_df["ASRS Group"] == "Group 2"]

    def _no_validated(sub):
        if target_col is None:
            return len(sub)
        return int((~sub[target_col].astype(str).str.lower().str.contains(
            "targets set|validated", na=False)).sum())

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Group 1 companies", len(g1_all),
              help="Mandatory from 1 Jan 2025 (FY2025/26 for June year-ends).")
    k2.metric("Group 1 BD prospects", _no_validated(g1_all),
              delta="reporting NOW", delta_color="inverse",
              help="Group 1 without a validated SBTi target.")
    k3.metric("Group 2 companies", len(g2_all),
              help="Mandatory from 1 Jul 2026.")
    k4.metric("Group 2 BD prospects", _no_validated(g2_all),
              delta="report FY2026/27", delta_color="off")
    sfg_count = int(asrs_df["Safeguard"].eq("Yes").sum()) if "Safeguard" in asrs_df.columns else 0
    k5.metric("Safeguard-covered", sfg_count,
              help="Companies with at least one Safeguard-covered facility.")

    st.markdown("---")

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 2, 1])
    with fc1:
        f_asrs_group = st.multiselect(
            "ASRS Group", ["Group 1", "Group 2", "Group 3", "Unclassified"],
            default=["Group 1", "Group 2"], key="asrs_screen_group",
        )
    with fc2:
        sector_opts = sorted(asrs_df[CANON["sector"]].dropna().unique())
        f_sector = st.multiselect("Sector", sector_opts, key="asrs_screen_sector")
    with fc3:
        tc_opts = sorted(asrs_df[target_col].dropna().unique()) if target_col else []
        f_target = st.multiselect("Target classification", tc_opts, key="asrs_screen_target")
    with fc4:
        f_sbti_tab = st.multiselect(
            "SBTi",
            ["Yes", "No"],
            default=[],
            key="asrs_screen_sbti",
            help="Yes = company has an SBTi entry (validated, committed, or removed). No = no SBTi engagement.",
        )
    with fc5:
        f_sfg_only = st.checkbox("Safeguard only", key="asrs_sfg_only")
        f_vol_only = st.checkbox("Has voluntary", key="asrs_vol_only")

    view = asrs_df.copy()
    if f_asrs_group:
        view = view[view["ASRS Group"].isin(f_asrs_group)]
    if f_sector:
        view = view[view[CANON["sector"]].isin(f_sector)]
    if f_target and target_col:
        view = view[view[target_col].isin(f_target)]
    if f_sbti_tab and "SBTi" in view.columns:
        view = view[view["SBTi"].isin(f_sbti_tab)]
    if f_sfg_only and "Safeguard" in view.columns:
        view = view[view["Safeguard"] == "Yes"]
    if f_vol_only:
        view = view[view["Voluntary Retirements (ACCUs)"].notna() &
                    (view["Voluntary Retirements (ACCUs)"] > 0)]
    if "BD Priority Score" in view.columns:
        view = view.sort_values("BD Priority Score", ascending=False)

    # ── Summary chart ─────────────────────────────────────────────────────────
    if not view.empty and target_col:
        grp_summary = (
            view.groupby(["ASRS Group", target_col]).size().reset_index(name="count")
        )
        _tc_order = ["No public target", "Aspirational", "Net-zero only",
                     "Quantitative non-validated", "SBTi committed", "Targets set"]
        fig = go.Figure()
        for tc in sorted(grp_summary[target_col].unique(),
                         key=lambda x: _tc_order.index(x) if x in _tc_order else 99):
            sub = grp_summary[grp_summary[target_col] == tc]
            fig.add_trace(go.Bar(x=sub["ASRS Group"], y=sub["count"], name=tc))
        fig.update_layout(
            barmode="stack", height=260,
            margin=dict(l=10, r=10, t=30, b=10),
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="Inter, Helvetica, sans-serif", size=11),
            title="Companies by ASRS Group and target status",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Main table ────────────────────────────────────────────────────────────
    # Truncate near-term target text for display
    if CANON["target"] in view.columns:
        view = view.copy()
        view["Near-term Target (short)"] = (
            view[CANON["target"]].astype(str).str[:120]
            .where(view[CANON["target"]].notna(), "—")
        )

    display_cols = [c for c in [
        CANON["company"],
        "ASX Code",
        "Listed",
        CANON["sector"],
        "ASRS Group",
        "NGER Reporter",
        CANON["near_term_status"],
        target_col or "Target Classification",
        "Near-term Target (short)",
        CANON["net_zero_year"],
        "Target Year (used)",
        "FY Year End",
        "First ASRS Report",
        "Safeguard",
        "Safeguard Covered (tCO2e)",
        "Safeguard Surrendered (tCO2e)",
        "Voluntary Retirements (ACCUs)",
        # NZT overlay columns (only present when NZT file uploaded)
        "NZT Status",
        "NZT End Target",
        "NZT End Year",
        "NZT Interim %",
        "NZT Published Plan",
        "NZT Race to Zero",
        "NZT Target Classification",
        "Research Source URL",
        "Profile Source",
        "BD Priority",
        "BD Rationale",
    ] if c and c in view.columns]

    st.markdown(f"**{len(view)} companies** match current filters")
    st.dataframe(
        view[display_cols].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            CANON["company"]: st.column_config.TextColumn(
                "Company",
                help="Company name as listed in the SBTi register or ASX 200 cohort.",
            ),
            "ASX Code": st.column_config.TextColumn(
                "ASX Code",
                help="ASX ticker code. Blank for private companies not listed on the ASX.",
            ),
            "Listed": st.column_config.TextColumn(
                "Listed",
                help="ASX Listed = traded on the Australian Securities Exchange. Private & Unlisted = private companies, foreign-owned subsidiaries, and NGER reporters not on ASX.",
            ),
            CANON["sector"]: st.column_config.TextColumn(
                "Sector",
                help="GICS or SBTi sector classification used to determine applicable guidance.",
            ),
            "NGER Reporter": st.column_config.TextColumn(
                "NGER Reporter",
                help=(
                    "Whether the company is an NGER reporter, and the basis:\n\n"
                    "• 'Yes — NGER register': appears directly in the NGER register (≥25kt CO₂e or ≥200TJ energy).\n"
                    "• 'Yes — Safeguard (inferred)': covered under the Safeguard Mechanism (≥100kt CO₂e), which implies NGER obligation. Not all Safeguard-covered companies will show NGER data separately.\n"
                    "• 'No': not identified as an NGER reporter from available data — may still be in scope at lower thresholds."
                ),
            ),
            "ASRS Group": st.column_config.TextColumn(
                "ASRS Group",
                help=(
                    "Mandatory ASRS reporting group under AASB S2 Climate-related Disclosures.\n\n"
                    "Group 1: mandatory from FY2025/26 (large entities).\n"
                    "Group 2: mandatory from FY2026/27.\n"
                    "Group 3: mandatory from FY2027/28."
                ),
            ),
            CANON["near_term_status"]: st.column_config.TextColumn(
                "SBTi Status",
                help=(
                    "Status in the SBTi register: 'Targets set' = validated near-term target, "
                    "'Committed' = intent letter submitted but not yet validated, "
                    "'Commitment removed' = lapsed commitment."
                ),
            ),
            target_col or "Target Classification": st.column_config.TextColumn(
                "Target Classification",
                help=(
                    "BD-assigned target classification: No public target, Aspirational, "
                    "Net-zero only, Quantitative non-validated, SBTi committed, or Targets set."
                ),
            ),
            "Near-term Target (short)": st.column_config.TextColumn(
                "Near-term Target",
                help="Full near-term SBTi target wording as submitted. Truncated to 120 chars.",
            ),
            CANON["net_zero_year"]: st.column_config.NumberColumn(
                "Net-Zero Year",
                format="%d",
                help="Year the company has committed to reach net-zero emissions.",
            ),
            "Target Year (used)": st.column_config.NumberColumn(
                "Target Year",
                format="%d",
                help="Near-term target year (from SBTi or research overlay).",
            ),
            "FY Year End": st.column_config.TextColumn(
                "FY Year End",
                help=(
                    "Financial year-end date for this entity. "
                    "Most ASX companies use 30 Jun; banks use 30 Sep; mining majors vary."
                ),
            ),
            "First ASRS Report": st.column_config.TextColumn(
                "First ASRS Report",
                help="First mandatory ASRS report period. FY end assumed 30 Jun unless known otherwise.",
            ),
            "Safeguard": st.column_config.TextColumn(
                "Safeguard",
                help="Yes if the company has at least one facility covered under the Safeguard Mechanism (100 kt CO₂e threshold).",
            ),
            "Safeguard Covered (tCO2e)": st.column_config.NumberColumn(
                "Safeguard Covered (tCO2e)",
                format="%,.0f",
                help="Total covered emissions (tCO₂e) across all Safeguard-covered facilities for this company.",
            ),
            "Safeguard Surrendered (tCO2e)": st.column_config.NumberColumn(
                "Safeguard Surrendered (tCO2e)",
                format="%,.0f",
                help="ACCUs + SMCs surrendered under the Safeguard Mechanism to meet baseline obligations.",
            ),
            "Voluntary Retirements (ACCUs)": st.column_config.NumberColumn(
                "Voluntary Retirements (ACCUs)",
                format="%,.0f",
                help="Total ACCUs voluntarily retired in the ANREU register (excludes Safeguard surrenders).",
            ),
            "Research Source URL": st.column_config.LinkColumn(
                "Source",
                help="Link to the sustainability report or SBTi disclosure used as the primary data source.",
            ),
            "Profile Source": st.column_config.TextColumn(
                "Profile Source",
                help=(
                    "Where this company's climate profile data comes from:\n\n"
                    "• 'SBTi Companies Taking Action': sourced directly from the SBTi public register.\n"
                    "• 'ASX 200 research cohort': manually researched for ASX 200 companies without SBTi targets.\n"
                    "• 'NGER register': sourced from the National Greenhouse and Energy Reporting dataset.\n"
                    "• '+ research overlay': target data has been updated or enriched with verified external research (PDF/URL).\n"
                    "• '+ Net Zero Tracker': Target Classification upgraded using Net Zero Tracker data for non-SBTi companies."
                ),
            ),
            "BD Priority": st.column_config.TextColumn(
                "BD Priority",
                help=(
                    "Overall BD priority based on two factors:\n\n"
                    "1. ASRS reporting urgency (Group 1 = reporting now, Group 2 = FY2026/27, Group 3 = FY2027/28)\n"
                    "2. Climate target gap (No public target = critical gap; Targets set = low urgency)\n\n"
                    "🔴 Critical = Group 1 + no/weak target\n"
                    "🟠 High = Group 1 with some target, or Group 2 with weak/no target\n"
                    "🟡 Medium = Group 2–3 with partial target\n"
                    "🟢 Low = validated SBTi target in place"
                ),
            ),
            "BD Rationale": st.column_config.TextColumn(
                "BD Rationale",
                help="Plain-English explanation of why this company is (or isn't) a BD priority. Combines ASRS reporting deadline with climate target gap. Safe to paste into a client prep note or BD briefing.",
            ),
            "NZT Status": st.column_config.TextColumn(
                "NZT Status",
                help="Net Zero Tracker status of end target: 'In corporate strategy', 'Declaration/pledge', or 'Proposed/in discussion'.",
            ),
            "NZT End Target": st.column_config.TextColumn(
                "NZT End Target",
                help="Type of end target as classified by the Net Zero Tracker (e.g. Net-zero emissions, Carbon neutral).",
            ),
            "NZT End Year": st.column_config.NumberColumn(
                "NZT Year",
                format="%d",
                help="Year by which the company has committed to reach its end target.",
            ),
            "NZT Interim %": st.column_config.NumberColumn(
                "NZT Interim %",
                format="%.0f%%",
                help="Interim GHG reduction percentage commitment (e.g. 42 = 42% reduction by interim year).",
            ),
            "NZT Published Plan": st.column_config.TextColumn(
                "NZT Plan",
                help="Whether the company has published a decarbonisation transition plan (Yes/No per NZT).",
            ),
            "NZT Race to Zero": st.column_config.TextColumn(
                "NZT Race to Zero",
                help="Whether the company is a member of the UN Race to Zero campaign.",
            ),
            "NZT Target Classification": st.column_config.TextColumn(
                "NZT Classification",
                help="BD Target Classification derived from NZT data (before any upgrade to the main Target Classification column).",
            ),
        },
    )

    st.download_button(
        "⬇ Download AUS Company Profile (CSV)",
        view[display_cols].to_csv(index=False).encode("utf-8"),
        file_name="aus_company_profile.csv",
        mime="text/csv",
    )
    st.caption(
        "⚠️ ASRS Group and FY Year End are indicative — derived from market cap tier proxy "
        "where financial data is unavailable. Verify against ASIC filings. "
        "Voluntary retirements include all ANREU cancellations matched by entity name "
        "(may include trading intermediaries)."
    )


with tab_safeguard:
    from modules.safeguard import load_safeguard

    st.markdown("### 🏭 Safeguard Mechanism — Register Overview")
    st.caption(
        "All facilities covered under the Safeguard Mechanism (CER register, FY2024-25). "
        "100 kt CO₂e threshold."
    )

    @st.cache_data(show_spinner="Loading Safeguard register…", ttl=600)
    def _load_safeguard_full():
        return load_safeguard()

    @st.cache_data(show_spinner="Loading ACCU surrender methods…", ttl=600)
    def _load_surrender_methods() -> pd.DataFrame:
        from pathlib import Path
        p = Path(__file__).resolve().parent / "data" / "cer" / "accu-surrender-methods.csv"
        if not p.exists():
            return pd.DataFrame()
        df = pd.read_csv(p, encoding="utf-8-sig")
        df.columns = df.columns.str.strip()
        rename = {
            "Responsible emitter": "responsible_emitter",
            "ACCU method type": "accu_method_type",
            "Quantity surrendered": "qty_surrendered",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        df["qty_surrendered"] = (
            df["qty_surrendered"].astype(str).str.replace(",", "").str.strip()
        )
        df["qty_surrendered"] = pd.to_numeric(df["qty_surrendered"], errors="coerce").fillna(0)
        return df

    if not safeguard_available():
        st.warning(
            "Safeguard register not loaded. Copy `baselines-and-emissions.csv` from the "
            "CER Safeguard register into `data/safeguard_baselines.csv` to enable this tab."
        )
    else:
        sfg_full = _load_safeguard_full()
        surrender_df = _load_surrender_methods()

        # ── Hero: Compliance Surrenders by Emitter ───────────────────────────
        if not surrender_df.empty:
            st.markdown("#### Compliance Surrenders by Emitter")
            st.caption("ACCUs surrendered under the Safeguard Mechanism, broken down by ACCU method type. Source: CER Safeguard register, FY2024-25.")

            # Pivot: rows = emitter, cols = method type, values = qty surrendered
            pivot = (
                surrender_df.groupby(["responsible_emitter", "accu_method_type"])["qty_surrendered"]
                .sum()
                .reset_index()
            )
            pivot_wide = pivot.pivot_table(
                index="responsible_emitter",
                columns="accu_method_type",
                values="qty_surrendered",
                aggfunc="sum",
                fill_value=0,
            )
            pivot_wide["Grand total"] = pivot_wide.sum(axis=1)
            pivot_wide = pivot_wide.sort_values("Grand total", ascending=False).reset_index()

            # Method type order (most common first)
            method_order = ["Vegetation", "Waste", "Savanna Fire Management",
                            "Industrial Fugitives", "Facilities", "Energy Efficiency", "Agriculture"]
            method_cols = [c for c in method_order if c in pivot_wide.columns]
            other_cols = [c for c in pivot_wide.columns
                         if c not in method_cols + ["responsible_emitter", "Grand total"]]
            ordered_cols = ["responsible_emitter"] + method_cols + other_cols + ["Grand total"]
            pivot_wide = pivot_wide[[c for c in ordered_cols if c in pivot_wide.columns]]

            # Add grand total row
            total_row = {c: pivot_wide[c].sum() if c != "responsible_emitter" else "Grand total"
                         for c in pivot_wide.columns}
            pivot_display = pd.concat(
                [pivot_wide, pd.DataFrame([total_row])], ignore_index=True
            )

            # Format numbers as "K" strings for display
            def _fmt_k(v):
                try:
                    f = float(v)
                    return f"{f/1000:.1f}K" if f >= 1000 else (f"{f:,.0f}" if f > 0 else "—")
                except (ValueError, TypeError):
                    return str(v)

            display_pivot = pivot_display.copy()
            for col in display_pivot.columns:
                if col != "responsible_emitter":
                    display_pivot[col] = display_pivot[col].apply(_fmt_k)

            col_cfg = {
                "responsible_emitter": st.column_config.TextColumn("Responsible Emitter", width="large"),
                "Grand total": st.column_config.TextColumn("Grand Total", width="small"),
            }
            for mc in method_cols + other_cols:
                col_cfg[mc] = st.column_config.TextColumn(mc, width="small")

            # Filters
            sf_c1, sf_c2 = st.columns(2)
            with sf_c1:
                method_filter = st.multiselect(
                    "Method type", method_cols + other_cols, key="sfg_method_filter",
                    help="Filter to specific ACCU method types.",
                )
            with sf_c2:
                top_n = st.slider("Show top N emitters", 5, len(pivot_wide), min(20, len(pivot_wide)),
                                  key="sfg_top_n")

            # Apply filters
            show_cols = method_filter if method_filter else (method_cols + other_cols)
            display_cols_pivot = ["responsible_emitter"] + [c for c in show_cols if c in display_pivot.columns] + ["Grand total"]
            display_pivot_filtered = display_pivot[display_cols_pivot].iloc[:top_n + 1]  # +1 for grand total row

            st.dataframe(
                display_pivot_filtered,
                use_container_width=True,
                hide_index=True,
                height=min(600, (top_n + 2) * 35 + 40),
                column_config=col_cfg,
            )

            st.download_button(
                "⬇ Download compliance surrenders (CSV)",
                pivot_wide.to_csv(index=False).encode("utf-8"),
                file_name="safeguard_compliance_surrenders.csv",
                mime="text/csv",
            )

            # ── Heatmap: Emitter × ACCU Method Type ─────────────────────────
            st.markdown("#### Compliance Surrenders — Heatmap")
            st.caption(
                "Colour intensity = ACCUs surrendered. "
                "Rows = top emitters by total surrenders; columns = ACCU method type. "
                "Hover for exact volume."
            )
            hm_top_n = st.slider(
                "Emitters to show", 5, min(40, len(pivot_wide)), min(25, len(pivot_wide)),
                key="sfg_hm_top_n",
            )
            hm_cols = method_cols + other_cols  # numeric method columns only
            hm_data = pivot_wide.head(hm_top_n).copy()
            hm_z = hm_data[[c for c in hm_cols if c in hm_data.columns]].values.tolist()
            hm_y = hm_data["responsible_emitter"].tolist()
            hm_x = [c for c in hm_cols if c in hm_data.columns]

            # Custom text labels on cells (show "—" for zero, "Xk" for thousands)
            def _hm_text(v):
                try:
                    f = float(v)
                    if f == 0:
                        return ""
                    return f"{f/1000:.0f}k" if f >= 1000 else f"{f:.0f}"
                except Exception:
                    return ""

            hm_text = [[_hm_text(v) for v in row] for row in hm_z]

            fig_hm = go.Figure(data=go.Heatmap(
                z=hm_z,
                x=hm_x,
                y=hm_y,
                text=hm_text,
                texttemplate="%{text}",
                colorscale=[
                    [0.0, "#F0F9FF"],
                    [0.2, "#BAE6FD"],
                    [0.5, "#38BDF8"],
                    [0.8, "#0369A1"],
                    [1.0, "#0C4A6E"],
                ],
                hovertemplate=(
                    "<b>%{y}</b><br>%{x}<br>%{z:,.0f} ACCUs<extra></extra>"
                ),
                colorbar=dict(title="ACCUs surrendered", thickness=14),
                xgap=2,
                ygap=1,
            ))
            fig_hm.update_layout(
                height=max(350, hm_top_n * 24 + 80),
                margin=dict(l=10, r=10, t=30, b=60),
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(family="Inter, Helvetica, sans-serif", size=10),
                xaxis=dict(side="bottom", tickangle=-30),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_hm, use_container_width=True)

            st.markdown("---")

        if sfg_full is None or sfg_full.empty:
            st.info("Safeguard register loaded but contains no rows.")
        else:
            # ── KPI row ──────────────────────────────────────────────────────
            total_fac = len(sfg_full)
            total_cov_mt = sfg_full["covered_emissions"].sum() / 1_000_000 if "covered_emissions" in sfg_full.columns else 0
            total_base_mt = sfg_full["baseline"].sum() / 1_000_000 if "baseline" in sfg_full.columns else 0
            total_accus_kt = sfg_full["accus_surrendered"].sum() / 1_000 if "accus_surrendered" in sfg_full.columns else 0
            above_base = int((sfg_full["net_position"] < 0).sum()) if "net_position" in sfg_full.columns else 0
            pct_above = above_base / total_fac * 100 if total_fac > 0 else 0

            sk1, sk2, sk3, sk4, sk5 = st.columns(5)
            sk1.metric("Total facilities", f"{total_fac:,}")
            sk2.metric("Total covered emissions", f"{total_cov_mt:.1f} Mt",
                       help="Sum of covered emissions across all facilities (Mt CO₂e).")
            sk3.metric("Total baseline", f"{total_base_mt:.1f} Mt",
                       help="Sum of assigned baselines across all facilities (Mt CO₂e).")
            sk4.metric("Total ACCUs surrendered", f"{total_accus_kt:.0f} kt",
                       help="Total ACCUs surrendered to meet Safeguard obligations.")
            sk5.metric("Facilities above baseline", f"{above_base:,} ({pct_above:.0f}%)",
                       help="Facilities where covered emissions exceed the assigned baseline (net_position < 0).")

            st.markdown("---")

            # ── Chart 1: Top 20 by covered emissions ─────────────────────────
            if "covered_emissions" in sfg_full.columns and "facility_name" in sfg_full.columns:
                st.markdown("**Top 20 facilities by covered emissions**")
                top20 = (
                    sfg_full.nlargest(20, "covered_emissions")
                    .sort_values("covered_emissions", ascending=True)
                )
                fig_top20 = px.bar(
                    top20,
                    y="facility_name",
                    x="covered_emissions",
                    orientation="h",
                    labels={"covered_emissions": "Covered emissions (tCO₂e)", "facility_name": "Facility"},
                    height=500,
                )
                fig_top20.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    plot_bgcolor="white", paper_bgcolor="white",
                    font=dict(family="Inter, Helvetica, sans-serif", size=11),
                )
                st.plotly_chart(fig_top20, use_container_width=True)

            # ── Chart 2: State breakdowns ─────────────────────────────────────
            if "state" in sfg_full.columns and "covered_emissions" in sfg_full.columns:
                ch2_left, ch2_right = st.columns(2)
                state_cov = (
                    sfg_full.groupby("state")["covered_emissions"].sum()
                    .reset_index()
                    .sort_values("covered_emissions", ascending=False)
                )
                with ch2_left:
                    st.markdown("**Covered emissions by state**")
                    fig_state_cov = px.bar(
                        state_cov,
                        x="state",
                        y="covered_emissions",
                        labels={"covered_emissions": "Covered emissions (tCO₂e)", "state": "State"},
                    )
                    fig_state_cov.update_layout(
                        margin=dict(l=10, r=10, t=30, b=10),
                        plot_bgcolor="white", paper_bgcolor="white",
                        font=dict(family="Inter, Helvetica, sans-serif", size=11),
                    )
                    st.plotly_chart(fig_state_cov, use_container_width=True)

                if "net_position" in sfg_full.columns:
                    with ch2_right:
                        st.markdown("**Net position by state**")
                        state_net = (
                            sfg_full.groupby("state")["net_position"].sum()
                            .reset_index()
                            .sort_values("net_position", ascending=False)
                        )
                        state_net["Status"] = state_net["net_position"].apply(
                            lambda v: "Compliant (below baseline)" if v >= 0 else "Shortfall (above baseline)"
                        )
                        fig_state_net = px.bar(
                            state_net,
                            x="state",
                            y="net_position",
                            color="Status",
                            color_discrete_map={
                                "Compliant (below baseline)": "#16A34A",
                                "Shortfall (above baseline)": "#DC2626",
                            },
                            labels={"net_position": "Net position (tCO₂e)", "state": "State"},
                        )
                        fig_state_net.update_layout(
                            margin=dict(l=10, r=10, t=30, b=10),
                            plot_bgcolor="white", paper_bgcolor="white",
                            font=dict(family="Inter, Helvetica, sans-serif", size=11),
                        )
                        st.plotly_chart(fig_state_net, use_container_width=True)

            # ── Chart 3: GHG composition by state ────────────────────────────
            ghg_cols = [c for c in ["ghg_co2", "ghg_ch4", "ghg_n2o", "ghg_other"]
                        if c in sfg_full.columns and sfg_full[c].sum() > 0]
            if ghg_cols and "state" in sfg_full.columns:
                st.markdown("**GHG composition across all facilities**")
                ghg_state = sfg_full.groupby("state")[ghg_cols].sum().reset_index()
                ghg_melt = ghg_state.melt(id_vars="state", value_vars=ghg_cols,
                                           var_name="GHG", value_name="tCO2e")
                ghg_melt["GHG"] = ghg_melt["GHG"].str.replace("ghg_", "").str.upper()
                fig_ghg = px.bar(
                    ghg_melt,
                    x="state",
                    y="tCO2e",
                    color="GHG",
                    barmode="stack",
                    labels={"tCO2e": "Emissions (tCO₂e)", "state": "State"},
                )
                fig_ghg.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    plot_bgcolor="white", paper_bgcolor="white",
                    font=dict(family="Inter, Helvetica, sans-serif", size=11),
                )
                st.plotly_chart(fig_ghg, use_container_width=True)

            # ── Chart 4: ACCUs vs SMCs + baseline scatter ─────────────────────
            ch4_left, ch4_right = st.columns(2)
            surr_cols = [c for c in ["accus_surrendered", "smcs_surrendered"]
                         if c in sfg_full.columns]
            if surr_cols and "state" in sfg_full.columns:
                with ch4_left:
                    st.markdown("**ACCUs vs SMCs surrendered by state**")
                    surr_state = sfg_full.groupby("state")[surr_cols].sum().reset_index()
                    surr_melt = surr_state.melt(id_vars="state", value_vars=surr_cols,
                                                 var_name="Type", value_name="tCO2e")
                    surr_melt["Type"] = surr_melt["Type"].str.replace("_surrendered", "").str.upper()
                    fig_surr = px.bar(
                        surr_melt,
                        x="state",
                        y="tCO2e",
                        color="Type",
                        barmode="group",
                        labels={"tCO2e": "Surrendered (tCO₂e)", "state": "State"},
                    )
                    fig_surr.update_layout(
                        margin=dict(l=10, r=10, t=30, b=10),
                        plot_bgcolor="white", paper_bgcolor="white",
                        font=dict(family="Inter, Helvetica, sans-serif", size=11),
                    )
                    st.plotly_chart(fig_surr, use_container_width=True)

            if "baseline" in sfg_full.columns and "covered_emissions" in sfg_full.columns:
                with ch4_right:
                    st.markdown("**Baseline vs Covered emissions**")
                    hover_cols = [c for c in ["facility_name", "responsible_emitter", "state"]
                                  if c in sfg_full.columns]
                    fig_scatter = px.scatter(
                        sfg_full,
                        x="baseline",
                        y="covered_emissions",
                        hover_data=hover_cols if hover_cols else None,
                        labels={
                            "baseline": "Baseline (tCO₂e)",
                            "covered_emissions": "Covered emissions (tCO₂e)",
                        },
                    )
                    # Add y = x diagonal reference line
                    axis_max = max(
                        sfg_full["baseline"].max(),
                        sfg_full["covered_emissions"].max(),
                    )
                    fig_scatter.add_shape(
                        type="line",
                        x0=0, y0=0, x1=axis_max, y1=axis_max,
                        line=dict(color="#94A3B8", width=1, dash="dash"),
                    )
                    fig_scatter.update_layout(
                        margin=dict(l=10, r=10, t=30, b=10),
                        plot_bgcolor="white", paper_bgcolor="white",
                        font=dict(family="Inter, Helvetica, sans-serif", size=11),
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)

            # ── Full facility table ───────────────────────────────────────────
            st.markdown("---")
            st.markdown("**Full facility register**")
            sfg_table_cols = [c for c in [
                "facility_name", "responsible_emitter", "state",
                "baseline", "covered_emissions",
                "accus_surrendered", "smcs_surrendered", "net_position",
            ] if c in sfg_full.columns]
            sfg_table = sfg_full[sfg_table_cols].copy()
            st.dataframe(
                sfg_table.reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
                height=520,
                column_config={
                    "facility_name": st.column_config.TextColumn("Facility"),
                    "responsible_emitter": st.column_config.TextColumn("Responsible Emitter"),
                    "state": st.column_config.TextColumn("State"),
                    "baseline": st.column_config.NumberColumn("Baseline (tCO₂e)", format="%,.0f"),
                    "covered_emissions": st.column_config.NumberColumn("Covered Emissions (tCO₂e)", format="%,.0f"),
                    "accus_surrendered": st.column_config.NumberColumn("ACCUs Surrendered", format="%,.0f"),
                    "smcs_surrendered": st.column_config.NumberColumn("SMCs Surrendered", format="%,.0f"),
                    "net_position": st.column_config.NumberColumn("Net Position (tCO₂e)", format="%+,.0f"),
                },
            )
            st.download_button(
                "⬇ Download Safeguard register (CSV)",
                sfg_table.to_csv(index=False).encode("utf-8"),
                file_name="safeguard_register.csv",
                mime="text/csv",
            )


with tab_brief:
    st.markdown("### Company Brief")
    st.caption(
        "One-page BD prep doc per company — everything we have on file in a single, "
        "copy-paste-ready briefing. Free, instant, no API calls. Pick a company below."
    )

    brief_names = sorted(screen[CANON["company"]].dropna().unique())
    chosen = st.selectbox(
        "Company",
        brief_names,
        key="brief_company_pick",
        help="Search by typing — covers the entire cohort.",
    )
    if chosen:
        rec = screen[screen[CANON["company"]] == chosen].iloc[0]
        brief_md = build_brief(rec, emissions_cache)
        st.markdown(brief_md)
        st.markdown("---")
        st.download_button(
            "⬇ Download brief (Markdown)",
            brief_md.encode("utf-8"),
            file_name=f"brief_{chosen.replace(' ', '_').replace('/', '-')}.md",
            mime="text/markdown",
        )
        with st.expander("📋 Show raw markdown (copy-paste into Notion / email / Slack)"):
            st.code(brief_md, language="markdown")


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


with tab_methodology:
    st.markdown("### 📖 Methodology — How We Built the Company Universe")
    st.caption(
        "This page explains the data sources, inclusion criteria, and analytical frameworks "
        "behind every number in this tracker. Share with colleagues before they use the data."
    )

    st.markdown("---")

    # ── Company Universe ──────────────────────────────────────────────────────
    st.markdown("#### Company Universe")

    n_total = len(screen)
    n_asx  = int((screen.get("Listed", pd.Series()) == "ASX Listed").sum())
    n_priv = int((screen.get("Listed", pd.Series()) == "Private & Unlisted").sum())
    n_sbti = int((screen.get("SBTi", pd.Series()) == "Yes").sum())
    n_sfg  = int(screen.get("Safeguard", pd.Series()).eq("Yes").sum()) if "Safeguard" in screen.columns else 0

    mu1, mu2, mu3, mu4, mu5 = st.columns(5)
    mu1.metric("Total companies", f"{n_total:,}")
    mu2.metric("ASX Listed", f"{n_asx:,}")
    mu3.metric("Private & Unlisted", f"{n_priv:,}")
    mu4.metric("SBTi participants", f"{n_sbti:,}")
    mu5.metric("Safeguard-covered", f"{n_sfg:,}")

    st.markdown("""
The tracker covers four cohorts that together represent the material corporate climate
disclosure universe for Australian-focused BD work:

| Cohort | Source | Inclusion criterion | Listed status |
|--------|--------|---------------------|---------------|
| **ASX Listed — SBTi** | SBTi Companies Taking Action register | Australian company, ASX-listed, any SBTi status | ASX Listed |
| **Private & Unlisted — SBTi** | SBTi Companies Taking Action register | Australian company, not ASX-listed, any SBTi status | Private & Unlisted |
| **ASX 200 — no SBTi target** | ASX 200 research cohort (manually compiled) | In ASX 200; no SBTi entry; researched target status | ASX Listed |
| **NGER reporters** | National Greenhouse and Energy Reporting register | NGER-obligated entity not already in the above cohorts | Private & Unlisted |

For display purposes, cohorts are simplified to **ASX Listed** and **Private & Unlisted** in the
AUS Company Profile tab, with SBTi participation as a separate filter.
""")

    st.markdown("---")

    # ── Data Sources ──────────────────────────────────────────────────────────
    st.markdown("#### Data Sources")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
**🌐 SBTi Companies Taking Action**
- Publisher: Science Based Targets initiative
- URL: [sciencebasedtargets.org/companies-taking-action](https://sciencebasedtargets.org/companies-taking-action)
- Update cadence: Approx. monthly
- What we use: Company name, ISIN, sector, near-term target status, near-term target wording, net-zero commitment, target year
- Filtering applied: Country = Australia + New Zealand; all SBTi statuses included (Targets set, Committed, Commitment removed)

**📋 ASX 200 Research Cohort**
- Publisher: Pollination internal research
- What we use: Company name, ASX code, sector, target classification (6-tier), near-term target text, net-zero year, research source URL
- Coverage: Large-cap ASX companies without an SBTi entry
- Limitation: Manually maintained — may lag latest disclosures by 1–3 months
""")
    with col_b:
        st.markdown("""
**🏭 CER Safeguard Mechanism Register**
- Publisher: Clean Energy Regulator (CER)
- URL: [cer.gov.au/markets/reports-and-data](https://cer.gov.au/markets/reports-and-data)
- File: `baselines-and-emissions.csv`
- What we use: Facility name, responsible emitter, state, baseline, covered emissions, ACCUs/SMCs surrendered, net position
- Threshold: 100 kt CO₂e covered emissions (FY2024-25 register)

**🌿 CER ANREU Voluntary Cancellations**
- Publisher: Clean Energy Regulator (CER)
- File: `voluntary-cancellations.csv`
- What we use: Entity name, number of ACCUs voluntarily cancelled (retired)
- Matching: Fuzzy name matching against cohort companies (normalise legal suffixes, first-token + overlap rule)

**📊 NGER Register**
- Publisher: Clean Energy Regulator (CER) — NGER Act
- What we use: Facility-level NGER reporters to identify large private companies not captured by SBTi or ASX research
""")

    st.markdown("---")

    # ── ASRS Grouping ─────────────────────────────────────────────────────────
    st.markdown("#### ASRS Group Assignment (Mandatory Climate Reporting)")
    st.markdown("""
Under the **Corporations Amendment (Sustainability Reporting) Act 2024**, Australian entities
must prepare AASB S2 Climate-related Financial Disclosures. Entities are assigned to one of
three groups based on meeting **≥ 2 of 3** size thresholds:

| | Group 1 | Group 2 | Group 3 |
|---|---|---|---|
| **Mandatory from** | 1 Jan 2025 | 1 Jul 2026 | 1 Jul 2027 |
| **First report covers** | FY2025/26 | FY2026/27 | FY2027/28 |
| **Revenue (AUD)** | ≥ $500M | ≥ $200M | ≥ $50M |
| **Gross assets (AUD)** | ≥ $1B | ≥ $500M | ≥ $25M |
| **Employees** | ≥ 500 | ≥ 500 | ≥ 100 |

**How groups are assigned in this tracker:**
1. If verified financial data (revenue / assets / employees) is on file → apply the thresholds directly
2. If no financial data → proxy from **Market Cap Tier** (ASX convention: Mega >$10B → Group 1; Large $2–10B → Group 1; Mid $300M–$2B → Group 2; Small/Micro → Group 3)
3. If neither is available → **Unclassified**

Cells showing "(proxy)" indicate a market-cap-based estimate, not verified financials.
""")

    st.markdown("---")

    # ── Target Classification ─────────────────────────────────────────────────
    st.markdown("#### Target Classification Taxonomy")
    st.markdown("""
Every company is assigned to one of six target classification tiers, ordered from most to
least climate-aligned. The classification drives the BD Priority calculation.

| Classification | Meaning | BD urgency |
|---|---|---|
| **Targets set** | Validated SBTi near-term target in place | Low — monitor for V2 reset or delivery gap |
| **SBTi committed** | Intent letter submitted to SBTi; validation pending | Low-medium — target pending validation |
| **Quantitative non-validated** | Has a specific quantitative target (e.g. "50% by 2030") but not SBTi-validated | Medium — needs pathway support |
| **Net-zero only** | Net-zero long-term commitment but no near-term science-based target | Medium-high — near-term gap |
| **Aspirational** | Vague qualitative commitment ("working towards net zero") | High — no credible pathway |
| **No public target** | No publicly available climate commitment | Critical — ASRS disclosure without any strategy |

SBTi status (Targets set / Committed / Commitment removed / blank) is pulled directly from the
SBTi register. The remaining classifications are assigned through Pollination research for the
ASX 200 non-SBTi cohort.
""")

    st.markdown("---")

    # ── BD Priority ───────────────────────────────────────────────────────────
    st.markdown("#### BD Priority")
    st.markdown("""
BD Priority combines **ASRS reporting urgency** and **climate target gap** into a single signal:

```
BD Priority Score = Target Classification Urgency × ASRS Group Multiplier
```

| Target classification | Urgency score |
|---|---|
| No public target | 5 |
| Aspirational | 4 |
| Net-zero only | 3 |
| Quantitative non-validated | 2 |
| SBTi committed | 1 |
| Targets set | 0 |

| ASRS Group | Multiplier |
|---|---|
| Group 1 | × 3 |
| Group 2 | × 2 |
| Group 3 / Unclassified | × 1 |

**Priority bands:** 🔴 Critical ≥ 12 · 🟠 High ≥ 8 · 🟡 Medium ≥ 4 · 🟢 Low < 4

The **BD Rationale** column translates this into plain English: e.g.
*"Group 1 — mandatory now (FY2025/26); no public climate target — ASRS disclosure without any strategy"*.
""")

    st.markdown("---")

    # ── Safeguard Matching ────────────────────────────────────────────────────
    st.markdown("#### Safeguard & Voluntary Retirement Matching")
    st.markdown("""
Safeguard and voluntary retirement data is matched to cohort companies by **fuzzy name matching**:

1. **Normalise** — strip legal suffixes (Limited, Ltd, Pty, Group, Holdings, Corporation, Australia),
   lowercase, collapse whitespace
2. **Exact match** — normalised company key = normalised emitter key
3. **First-token + overlap match** — same first word AND ≥ 2 tokens in common (or min(2, len) tokens
   if the company name is short)
4. **Prefix match** — emitter name starts with the first 6+ characters of the company key

Limitations: matching fails for companies that operate under a completely different trading name
vs legal entity name (e.g. subsidiaries with distinct brands). Where a Safeguard match is
unexpected, check the **Safeguard Covered** column against the CER register directly.
""")

    st.markdown("---")

    # ── What's Not Captured ───────────────────────────────────────────────────
    st.markdown("#### Known Gaps")
    st.markdown("""
| Gap | Why | Workaround |
|---|---|---|
| **Financed emissions** (banks, super funds) | Scope 3 Cat. 15 not in Safeguard register; no AU mandatory financed-emissions dataset yet | Covered by sector filter — Financial Services companies in cohort via SBTi/ASX 200 |
| **Small-cap ASX companies** (outside ASX 200) | Not manually researched | ASRS Group 3 from 2027; low BD priority currently |
| **Private companies below NGER threshold** | No public disclosure obligation below 25 kt Scope 1+2 | Not material for Safeguard/ASRS BD work |
| **Non-Australian multinationals** | Tracker scoped to AU-domiciled entities | International parent companies excluded by design |
| **SBTi data lag** | SBTi register updated ~monthly; between updates, new commitments may not appear | Check [sciencebasedtargets.org](https://sciencebasedtargets.org/companies-taking-action) for latest |

Last data refresh: see sidebar → 📁 Data sources for upload dates.
""")

    st.markdown("---")

    # ── NGER Reporter Logic ───────────────────────────────────────────────────
    st.markdown("#### NGER Reporter Column Logic")
    st.markdown("""
The **NGER Reporter** column has three possible values:

- **Yes — NGER register**: Company was added to the tracker because it appeared in the NGER
  reporters file (cohort = "NGER reporters (not in cohort)")
- **Yes — Safeguard (inferred)**: Company is in the SBTi or ASX 200 cohort AND has a matched
  Safeguard facility. All Safeguard-covered entities are NGER-obligated (Safeguard threshold
  100 kt CO₂e is well above NGER's 25 kt threshold)
- **No**: No evidence of NGER obligation from either the NGER register or the Safeguard register

Note: A company showing "NGER Yes + Safeguard No" is not an error — it means the company
files NGER reports (likely 25–100 kt range) but does not cross the 100 kt Safeguard threshold.
""")


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


# ─── Philippines tab ──────────────────────────────────────────────────────────

def _render_country_profile_tab(
    country_label: str,
    flag: str,
    exchange_label: str,
    exchange_df: pd.DataFrame,
    sbti_country_df: pd.DataFrame,
    exchange_name_col: str,
    tier_fn,
    tier_col_label: str,
    tier_options: list[str],
    sector_col: str,
    extra_display_cols: list[str],
    extra_col_config: dict,
    download_filename: str,
    source_note: str,
    link_col: str | None = None,
):
    """Shared renderer for the Philippines and Malaysia BD profile tabs.

    Renders directly into the calling tab context (caller must be inside the
    correct ``with tab_XXX:`` block).  Builds an AUS-style company profile view
    with SBTi overlay, target classification, BD priority scoring, and filters.
    """
    from modules.country_profile import build_country_profile
    from modules.sbti import CANON as _CANON

    # Build enriched profile
    @st.cache_data(show_spinner=f"Building {country_label} BD profile…", ttl=1800)
    def _build_profile(
        _exch_hash: int, _sbti_hash: int,
        _exch_name_col: str, _tier_col: str,
    ) -> pd.DataFrame:
        return build_country_profile(
            exchange_df, sbti_country_df,
            exchange_name_col=_exch_name_col,
            tier_fn=tier_fn,
            tier_col_label=_tier_col,
        )

    profile = _build_profile(
        hash(tuple(exchange_df["Company Name"].dropna().astype(str).tolist())),
        hash(tuple(sbti_country_df["Company Name"].dropna().astype(str).tolist())
             if not sbti_country_df.empty else ()),
        exchange_name_col,
        tier_col_label,
    )

    # ── KPI row ────────────────────────────────────────────────────────────────
    n_total = len(profile)
    n_sbti = int((profile.get("SBTi", pd.Series()) == "Yes").sum())
    sbti_rate = f"{n_sbti / n_total * 100:.1f}%" if n_total else "—"
    n_no_target = int((profile.get("Target Classification", pd.Series()) == "No public target").sum())
    n_critical = int((profile.get("BD Priority", pd.Series()) == "🔴 Critical").sum())

    pk1, pk2, pk3, pk4, pk5 = st.columns(5)
    pk1.metric(f"Total {exchange_label}", f"{n_total:,}")
    pk2.metric("SBTi engaged", f"{n_sbti}",
               help="Companies with an entry in the SBTi Companies Taking Action register.")
    pk3.metric("SBTi rate", sbti_rate,
               help="Share of listed companies with any SBTi engagement.")
    pk4.metric("No public target", f"{n_no_target}",
               delta="BD prospects", delta_color="inverse",
               help="Companies with no public climate target — strongest BD signal.")
    pk5.metric("🔴 Critical priority", f"{n_critical}",
               help="Critical BD priority: large-cap + no/weak climate target.")

    st.markdown("---")

    # ── Summary chart: companies by tier and target status ─────────────────────
    if "Target Classification" in profile.columns and tier_col_label in profile.columns:
        _tc_order = ["No public target", "Aspirational", "Net-zero only",
                     "Quantitative non-validated", "SBTi committed", "Targets set"]
        grp_summary = (
            profile.groupby([tier_col_label, "Target Classification"])
            .size().reset_index(name="count")
        )
        fig_summary = go.Figure()
        for tc in sorted(grp_summary["Target Classification"].unique(),
                         key=lambda x: _tc_order.index(x) if x in _tc_order else 99):
            sub = grp_summary[grp_summary["Target Classification"] == tc]
            fig_summary.add_trace(go.Bar(
                x=sub[tier_col_label], y=sub["count"], name=tc,
            ))
        fig_summary.update_layout(
            barmode="stack", height=260,
            margin=dict(l=10, r=10, t=30, b=10),
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="Inter, Helvetica, sans-serif", size=11),
            title=f"Companies by {tier_col_label} and target status",
        )
        st.plotly_chart(fig_summary, use_container_width=True)

    # ── Filters ────────────────────────────────────────────────────────────────
    _fkey = country_label.lower().replace(" ", "_")
    ff1, ff2, ff3, ff4, ff5 = st.columns([2, 2, 2, 2, 1])
    with ff1:
        f_tier = st.multiselect(tier_col_label, tier_options, key=f"{_fkey}_tier")
    with ff2:
        sec_opts = sorted(profile[sector_col].dropna().unique()) if sector_col in profile.columns else []
        f_sector = st.multiselect("Sector", sec_opts, key=f"{_fkey}_sector")
    with ff3:
        tc_opts = sorted(profile["Target Classification"].dropna().unique()) if "Target Classification" in profile.columns else []
        f_target = st.multiselect("Target classification", tc_opts, key=f"{_fkey}_target")
    with ff4:
        f_sbti = st.multiselect("SBTi", ["Yes", "No"], key=f"{_fkey}_sbti",
                                help="Yes = company has an SBTi entry. No = no SBTi engagement.")
    with ff5:
        f_search = st.text_input("🔍 Search", key=f"{_fkey}_search")

    view = profile.copy()
    if f_tier and tier_col_label in view.columns:
        view = view[view[tier_col_label].isin(f_tier)]
    if f_sector and sector_col in view.columns:
        view = view[view[sector_col].isin(f_sector)]
    if f_target and "Target Classification" in view.columns:
        view = view[view["Target Classification"].isin(f_target)]
    if f_sbti and "SBTi" in view.columns:
        view = view[view["SBTi"].isin(f_sbti)]
    if f_search:
        mask = view["Company Name"].astype(str).str.contains(f_search, case=False, na=False)
        view = view[mask]
    if "BD Priority Score" in view.columns:
        view = view.sort_values("BD Priority Score", ascending=False)

    # Truncate near-term target text
    if _CANON["target"] in view.columns:
        view = view.copy()
        view["Near-term Target (short)"] = (
            view[_CANON["target"]].astype(str).str[:120]
            .where(view[_CANON["target"]].notna(), "—")
        )

    st.markdown(f"**{len(view)} companies** match current filters")

    # ── Main table ─────────────────────────────────────────────────────────────
    _base_cols = [
        "Company Name",
        tier_col_label,
        sector_col,
        "SBTi",
        _CANON["near_term_status"],
        "Target Classification",
        "Near-term Target (short)",
        _CANON["net_zero_year"],
        "BD Priority",
        "BD Rationale",
        "Profile Source",
    ]
    display_cols = [c for c in _base_cols + extra_display_cols
                    if c and c in view.columns]
    if link_col and link_col in view.columns and link_col not in display_cols:
        display_cols.append(link_col)

    _base_col_config = {
        "Company Name": st.column_config.TextColumn("Company", width="large"),
        tier_col_label: st.column_config.TextColumn(
            tier_col_label,
            help="Exchange tier / market segment used for BD priority weighting.",
        ),
        sector_col: st.column_config.TextColumn("Sector"),
        "SBTi": st.column_config.TextColumn(
            "SBTi",
            help="Yes = company has an entry in the SBTi Companies Taking Action register.",
        ),
        _CANON["near_term_status"]: st.column_config.TextColumn(
            "SBTi Status",
            help="Targets set / Committed / Commitment removed.",
        ),
        "Target Classification": st.column_config.TextColumn(
            "Target Classification",
            help="Six-tier BD target classification from No public target → Targets set.",
        ),
        "Near-term Target (short)": st.column_config.TextColumn(
            "Near-term Target",
            help="SBTi near-term target wording (truncated to 120 chars).",
        ),
        _CANON["net_zero_year"]: st.column_config.NumberColumn(
            "Net-Zero Year", format="%d",
            help="Year the company has committed to reach net-zero emissions.",
        ),
        "BD Priority": st.column_config.TextColumn(
            "BD Priority",
            help=(
                "BD priority combining exchange tier and climate target gap.\n\n"
                "🔴 Critical = large-cap + no/weak target\n"
                "🟠 High = mid-cap + weak target\n"
                "🟡 Medium = any tier with partial target\n"
                "🟢 Low = SBTi validated"
            ),
        ),
        "BD Rationale": st.column_config.TextColumn(
            "BD Rationale",
            help="Plain-English BD rationale combining reporting deadline and target gap.",
        ),
        "Profile Source": st.column_config.TextColumn(
            "Profile Source",
            help="SBTi Companies Taking Action = matched to SBTi register. Exchange listing only = no SBTi match found.",
        ),
    }
    if link_col:
        _base_col_config[link_col] = st.column_config.LinkColumn(
            "Exchange →", display_text="View", width="small"
        )
    col_config = {**_base_col_config, **extra_col_config}

    st.dataframe(
        view[display_cols].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config=col_config,
    )

    st.download_button(
        f"⬇ Download {country_label} BD Profile (CSV)",
        view[display_cols].to_csv(index=False).encode("utf-8"),
        file_name=download_filename,
        mime="text/csv",
    )

    st.markdown("---")
    st.caption(source_note)


with tab_philippines:
    from modules.pse import load_pse_companies, get_pse_board, PSE_SECTOR_ORDER, PSE_SECTOR_COLORS
    from modules.country_profile import filter_sbti_country

    @st.cache_data(show_spinner="Loading PSE company directory…", ttl=3600)
    def _load_pse() -> pd.DataFrame:
        try:
            return load_pse_companies()
        except Exception as exc:
            return pd.DataFrame({"error": [str(exc)]})

    pse_raw = _load_pse()

    if pse_raw.empty or "error" in pse_raw.columns:
        err = pse_raw["error"].iloc[0] if "error" in pse_raw.columns else "Unknown error"
        st.markdown("### 🇵🇭 Philippines — BD Company Profile")
        st.error(
            f"Could not load PSE directory: {err}\n\n"
            "Check that data/pse_companies.csv is present, or that the PSE Edge API is reachable."
        )
    else:
        st.markdown("### 🇵🇭 Philippines — BD Company Profile")
        st.caption(
            "All PSE-listed companies matched against the global SBTi register, with BD priority "
            "scoring based on exchange tier and climate target gap. Same methodology as AUS Company Profile."
        )

        @st.cache_data(show_spinner=False)
        def _pse_sbti(sbti_hash: int) -> pd.DataFrame:
            return filter_sbti_country(sbti_df, "Philippines", isin_prefix="PH")

        sbti_ph = _pse_sbti(hash(tuple(sbti_df["Company Name"].dropna().astype(str).tolist())))

        _render_country_profile_tab(
            country_label="Philippines",
            flag="🇵🇭",
            exchange_label="PSE",
            exchange_df=pse_raw,
            sbti_country_df=sbti_ph,
            exchange_name_col="Company Name",
            tier_fn=get_pse_board,
            tier_col_label="PSE Board",
            tier_options=["PSE Main Board", "PSE SME Board"],
            sector_col="Sector",
            extra_display_cols=["Symbol", "Subsector", "Listing Date", "PSE Link"],
            extra_col_config={
                "Symbol": st.column_config.TextColumn("Symbol", width="small"),
                "Subsector": st.column_config.TextColumn("Subsector", width="medium"),
                "Listing Date": st.column_config.DateColumn("Listed", format="DD MMM YYYY", width="small"),
            },
            download_filename="philippines_bd_profile.csv",
            source_note=(
                "**Sources:** PSE listed company directory · SBTi Companies Taking Action register. "
                "PSE Board (Main / SME) sourced from PSE official listing data. "
                "SBTi matching is fuzzy — verify matches before client use. "
                "Target Classification for non-SBTi companies defaults to 'No public target'; "
                "this can be improved with a research overlay."
            ),
            link_col="PSE Link",
        )


# ─── Malaysia tab ─────────────────────────────────────────────────────────────

with tab_malaysia:
    from modules.bursa import (
        load_bursa_companies, get_bursa_tier,
        BURSA_MARKET_ORDER, BURSA_MARKET_COLORS, is_available as bursa_available,
    )
    from modules.country_profile import filter_sbti_country as _filter_sbti_country

    st.markdown("### 🇲🇾 Malaysia — BD Company Profile")
    st.caption(
        "All Bursa-listed companies matched against the global SBTi register, with BD priority "
        "scoring based on Bursa Market tier and climate target gap. Same methodology as AUS Company Profile."
    )

    # ── Data source: upload or local file ─────────────────────────────────────
    _bursa_available = bursa_available()

    if not _bursa_available:
        st.info(
            "**Bursa Malaysia company data required.**\n\n"
            "Bursa Malaysia's public APIs are not available for automated access. "
            "To enable this tab:\n\n"
            "1. Go to [Bursa Malaysia Listed Companies](https://www.bursamalaysia.com/market/listed-companies/list-of-listed-company/listed_companies_directory)\n"
            "2. Download the company list as CSV or Excel\n"
            "3. Upload it below (or commit to `data/bursa_companies.csv`)"
        )

    bursa_upload = st.file_uploader(
        "Upload Bursa Malaysia company list (CSV or Excel)",
        type=["csv", "xlsx", "xls"],
        key="bursa_upload",
        help="Download from the Bursa Malaysia listed companies directory. "
             "Expected columns: Company Name, Symbol, Market (Main/ACE/LEAP), Sector, ISIN.",
    )

    @st.cache_data(show_spinner="Loading Bursa company directory…", ttl=3600)
    def _load_bursa(file_bytes: bytes | None, file_name: str | None) -> pd.DataFrame:
        import io as _io
        if file_bytes is not None:
            buf = _io.BytesIO(file_bytes)
            buf.name = file_name or "bursa.csv"
            return load_bursa_companies(buf)
        return load_bursa_companies(None)

    bursa_raw = _load_bursa(
        bursa_upload.getvalue() if bursa_upload else None,
        bursa_upload.name if bursa_upload else None,
    )

    if bursa_raw.empty:
        if _bursa_available or bursa_upload:
            st.error("Could not parse the uploaded file. Check it has Company Name, Symbol, Market, and Sector columns.")
        # Otherwise the info box above is already showing — nothing more to do
    else:
        @st.cache_data(show_spinner=False)
        def _my_sbti(sbti_hash: int) -> pd.DataFrame:
            return _filter_sbti_country(sbti_df, "Malaysia", isin_prefix="MY")

        sbti_my = _my_sbti(hash(tuple(sbti_df["Company Name"].dropna().astype(str).tolist())))

        _render_country_profile_tab(
            country_label="Malaysia",
            flag="🇲🇾",
            exchange_label="Bursa",
            exchange_df=bursa_raw,
            sbti_country_df=sbti_my,
            exchange_name_col="Company Name",
            tier_fn=get_bursa_tier,
            tier_col_label="Bursa Market",
            tier_options=BURSA_MARKET_ORDER,
            sector_col="Sector",
            extra_display_cols=["Symbol", "ISIN", "Listing Date", "Bursa Link"],
            extra_col_config={
                "Symbol": st.column_config.TextColumn("Symbol", width="small"),
                "ISIN": st.column_config.TextColumn("ISIN", width="medium"),
                "Listing Date": st.column_config.DateColumn("Listed", format="DD MMM YYYY", width="small"),
            },
            download_filename="malaysia_bd_profile.csv",
            source_note=(
                "**Sources:** Bursa Malaysia listed companies directory · SBTi Companies Taking Action register. "
                "Bursa Market tier: Main Market = mandatory Bursa Sustainability Reporting (enhanced from 2023); "
                "ACE Market = enhanced requirements from 2026; LEAP Market = voluntary. "
                "SBTi matching is fuzzy — verify matches before client use. "
                "Target Classification for non-SBTi companies defaults to 'No public target'."
            ),
            link_col="Bursa Link",
        )
