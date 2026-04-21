"""
AASB S2 Climate Risk Disclosure Tool
Multi-client Streamlit application for consultants.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from io import BytesIO

from modules.client import (
    list_clients, load_client, save_client, new_client,
    delete_client, rename_safe, ENTITY_TYPES, INDUSTRIES,
)
from modules.framework import FRAMEWORK, PILLAR_DATA_KEYS
from modules.scoring import (
    score_overall, score_pillar,
    STATUS_LABELS, STATUS_COLORS, STATUS_BG,
)
from modules.disclosure import generate_pillar_disclosures, generate_all_disclosures
from modules.pdf_export import generate_pdf
from modules.carbon_registry import (
    load_project_register, load_safeguard_data, load_contract_register,
    summarise_developers, summarise_retirements, DOWNLOAD_INSTRUCTIONS,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AASB S2 Climate Disclosure Tool",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background-color: #0F172A; }
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label { color: #94A3B8 !important; }
.req-card {
    background: #F8FAFC;
    border-left: 4px solid #3B82F6;
    border-radius: 0 6px 6px 0;
    padding: 0.75rem 1rem 0.5rem 1rem;
    margin-bottom: 0.75rem;
}
.status-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 4px;
}
.disc-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    font-size: 0.88rem;
    line-height: 1.55;
    white-space: pre-wrap;
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

PILLAR_ICONS = {
    "Governance": "🏛️",
    "Strategy": "🎯",
    "Risk Management": "⚠️",
    "Metrics & Targets": "📊",
}

PAGES = [
    "Overview",
    "Governance",
    "Strategy",
    "Risk Management",
    "Metrics & Targets",
    "Gap Assessment",
    "Disclosure Drafts",
    "Export",
    "Carbon Market Registry",
]

# ── Session state init ─────────────────────────────────────────────────────────
if "client_data" not in st.session_state:
    st.session_state.client_data = None
if "page" not in st.session_state:
    st.session_state.page = "Overview"
if "widget_init_key" not in st.session_state:
    st.session_state.widget_init_key = None


def _init_widgets(client_data: dict) -> None:
    """Pre-populate all widget keys from loaded client data."""
    for pillar_name, pillar_info in FRAMEWORK.items():
        pillar_key = PILLAR_DATA_KEYS[pillar_name]
        for req in pillar_info["requirements"]:
            rid = req["id"]
            req_data = client_data.get(pillar_key, {}).get(rid, {})
            st.session_state[f"status_{rid}"] = req_data.get("status", "")
            st.session_state[f"notes_{rid}"] = req_data.get("notes", "")
            data = req_data.get("data", {})
            for field in req.get("fields", []):
                st.session_state[f"data_{rid}_{field['key']}"] = data.get(field["key"], "")


def _collect_widgets_into_client(client_data: dict) -> dict:
    """Read all widget states back into the client data dict."""
    for pillar_name, pillar_info in FRAMEWORK.items():
        pillar_key = PILLAR_DATA_KEYS[pillar_name]
        if pillar_key not in client_data:
            client_data[pillar_key] = {}
        for req in pillar_info["requirements"]:
            rid = req["id"]
            status = st.session_state.get(f"status_{rid}", "")
            notes = st.session_state.get(f"notes_{rid}", "")
            data = {
                field["key"]: st.session_state.get(f"data_{rid}_{field['key']}", "")
                for field in req.get("fields", [])
            }
            client_data[pillar_key][rid] = {
                "status": status,
                "notes": notes,
                "data": data,
            }
    return client_data


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌍 AASB S2 Tool")
    st.markdown("---")

    # ── Client selector ──────────────────────────────────────────────────────
    st.markdown("**Client**")
    clients = list_clients()
    client_options = ["— select —"] + clients + ["+ New client"]
    chosen = st.selectbox("Client", client_options, label_visibility="collapsed",
                          key="sidebar_client_select")

    if chosen == "+ New client":
        with st.form("new_client_form"):
            st.markdown("**Create new client**")
            nc_name = st.text_input("Client / entity name")
            nc_type = st.selectbox("Entity type", ENTITY_TYPES)
            nc_industry = st.selectbox("Industry", INDUSTRIES)
            nc_period = st.text_input("Reporting period", placeholder="e.g. FY2025")
            submitted = st.form_submit_button("Create")
            if submitted and nc_name.strip():
                safe_name = rename_safe(nc_name.strip())
                if safe_name in clients:
                    st.error("A client with that name already exists.")
                else:
                    cd = new_client(safe_name, nc_type, nc_industry, nc_period)
                    save_client(cd)
                    st.session_state.client_data = cd
                    st.session_state.widget_init_key = safe_name
                    _init_widgets(cd)
                    st.rerun()

    elif chosen != "— select —":
        if st.session_state.widget_init_key != chosen:
            cd = load_client(chosen)
            if cd:
                st.session_state.client_data = cd
                st.session_state.widget_init_key = chosen
                _init_widgets(cd)

    # ── Save / Delete ────────────────────────────────────────────────────────
    if st.session_state.client_data:
        cd = st.session_state.client_data
        st.caption(
            f"**{cd['client_name']}**  \n"
            f"{cd.get('entity_type','')}"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save", use_container_width=True):
                _collect_widgets_into_client(st.session_state.client_data)
                save_client(st.session_state.client_data)
                st.success("Saved")
        with col2:
            if st.button("🗑️ Delete", use_container_width=True):
                delete_client(cd["client_name"])
                st.session_state.client_data = None
                st.session_state.widget_init_key = None
                st.rerun()

    st.markdown("---")

    # ── Navigation ───────────────────────────────────────────────────────────
    st.markdown("**Navigation**")
    for pg in PAGES:
        icon = PILLAR_ICONS.get(pg, "")
        label = f"{icon} {pg}" if icon else pg
        if st.button(label, use_container_width=True,
                     type="primary" if st.session_state.page == pg else "secondary"):
            st.session_state.page = pg

    st.markdown("---")
    st.caption("AASB S2 Climate-Related Financial Disclosures  \n"
               "Mandatory for large entities from 2025")


# ── Guard: require a client ────────────────────────────────────────────────────
def _require_client() -> bool:
    if not st.session_state.client_data:
        st.info("Select or create a client in the sidebar to begin.")
        return False
    return True


# ── Helper widgets ─────────────────────────────────────────────────────────────
def _status_badge(status: str) -> str:
    label = STATUS_LABELS.get(status, "Not Assessed")
    color = STATUS_COLORS.get(status, "#9CA3AF")
    bg = STATUS_BG.get(status, "#F3F4F6")
    return (
        f'<span class="status-badge" style="background:{bg};color:{color}">'
        f'{label}</span>'
    )


def _render_field(rid: str, field: dict) -> None:
    key = f"data_{rid}_{field['key']}"
    ftype = field.get("type", "text")
    label = field["label"]

    if ftype == "textarea":
        st.text_area(label, key=key, placeholder=field.get("placeholder", ""),
                     height=90)
    elif ftype == "select":
        options = field.get("options", [""])
        current = st.session_state.get(key, "")
        idx = options.index(current) if current in options else 0
        st.selectbox(label, options, index=idx, key=key)
    else:
        st.text_input(label, key=key, placeholder=field.get("placeholder", ""))


def _render_requirement(req: dict, pillar_color: str) -> None:
    rid = req["id"]
    status = st.session_state.get(f"status_{rid}", "")

    with st.expander(
        f"**{rid}** – {req['title']}  {_status_badge(status)}",
        expanded=(status in ("", "not_met")),
    ):
        st.caption(f"{req['ref']}  |  {req['description']}")
        cols = st.columns([2, 5])
        with cols[0]:
            status_options = ["", "not_met", "partial", "met"]
            status_labels_map = {
                "": "Not Assessed",
                "not_met": "Not Met",
                "partial": "Partial",
                "met": "Met",
            }
            current_idx = status_options.index(st.session_state.get(f"status_{rid}", ""))
            new_status = st.selectbox(
                "Assessment status",
                status_options,
                index=current_idx,
                format_func=lambda v: status_labels_map[v],
                key=f"status_{rid}",
            )
        with cols[1]:
            st.text_area("Notes / evidence", key=f"notes_{rid}",
                         placeholder="Supporting evidence, caveats or next steps…",
                         height=68)

        st.markdown("**Data fields**")
        for field in req.get("fields", []):
            _render_field(rid, field)


# ── Pages ──────────────────────────────────────────────────────────────────────

def page_overview() -> None:
    st.title("🌍 AASB S2 Climate Risk Disclosure Tool")
    st.markdown(
        "Assess your client's climate-related financial disclosures against all four "
        "pillars of **AASB S2** (Climate-related Financial Disclosures). "
        "Navigate using the sidebar."
    )

    if not st.session_state.client_data:
        st.info("Select or create a client in the sidebar to begin.")
        st.markdown("---")
        st.markdown("#### About this tool")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**What it covers**
- All four AASB S2 pillars: Governance, Strategy, Risk Management, Metrics & Targets
- 19 individual disclosure requirements mapped to AASB S2 paragraphs
- Multi-client support with JSON file storage
""")
        with col2:
            st.markdown("""
**What it produces**
- Gap assessment with maturity scoring
- Draft AASB S2-aligned disclosure text
- Board-ready PDF report with remediation roadmap
- Printable disclosure drafts
""")
        return

    cd = st.session_state.client_data
    _collect_widgets_into_client(cd)
    overall = score_overall(cd)

    st.markdown(f"### {cd['client_name']}")
    st.caption(
        f"{cd.get('entity_type','')}  |  {cd.get('industry','')}  |  "
        f"Reporting period: {cd.get('reporting_period','')}"
    )
    st.markdown("---")

    # KPI row
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Overall Score", f"{overall['overall_pct']:.0f}%", overall["maturity_label"])
    kpi_cols[1].metric("Total Points", f"{overall['total_score']} / {overall['max_score']}")

    total_req = sum(ps["req_count"] for ps in overall["pillars"].values())
    total_met = sum(ps["met_count"] for ps in overall["pillars"].values())
    total_partial = sum(ps["partial_count"] for ps in overall["pillars"].values())
    total_gaps = total_req - total_met - total_partial

    kpi_cols[2].metric("Requirements Met", total_met)
    kpi_cols[3].metric("Partial", total_partial)
    kpi_cols[4].metric("Gaps to Address", total_gaps)

    st.markdown("---")

    # Pillar radar / bar chart
    pillar_names = list(FRAMEWORK.keys())
    pillar_pcts = [overall["pillars"][p]["percentage"] for p in pillar_names]
    bar_colors = [FRAMEWORK[p]["bar_color"] for p in pillar_names]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=pillar_names,
        y=pillar_pcts,
        marker_color=bar_colors,
        text=[f"{v:.0f}%" for v in pillar_pcts],
        textposition="outside",
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        yaxis=dict(range=[0, 110], ticksuffix="%", gridcolor="#F1F5F9"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=320,
        margin=dict(l=10, r=10, t=20, b=10),
        showlegend=False,
        font=dict(family="Inter, Helvetica, sans-serif", size=12),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Pillar cards
    cols = st.columns(4)
    for i, pillar_name in enumerate(FRAMEWORK):
        ps = overall["pillars"][pillar_name]
        with cols[i]:
            icon = PILLAR_ICONS[pillar_name]
            st.markdown(
                f"**{icon} {pillar_name}**  \n"
                f"{ps['percentage']:.0f}% – *{ps['maturity_label']}*  \n"
                f"Met: **{ps['met_count']}** | Partial: **{ps['partial_count']}** | "
                f"Gaps: **{ps['req_count'] - ps['met_count'] - ps['partial_count']}**"
            )


def page_pillar_form(pillar_name: str) -> None:
    if not _require_client():
        return

    info = FRAMEWORK[pillar_name]
    icon = PILLAR_ICONS[pillar_name]
    st.title(f"{icon} {pillar_name}")
    st.caption(info["description"])

    cd = st.session_state.client_data
    ps = score_pillar(cd, pillar_name)

    prog_col, score_col = st.columns([4, 1])
    with prog_col:
        st.progress(ps["percentage"] / 100,
                    text=f"{ps['percentage']:.0f}%  –  {ps['maturity_label']}")
    with score_col:
        st.metric("Score", f"{ps['score']} / {ps['max_score']}")

    st.markdown("---")

    for req in info["requirements"]:
        _render_requirement(req, info["bar_color"])

    st.markdown("---")
    if st.button("💾 Save progress", type="primary"):
        _collect_widgets_into_client(st.session_state.client_data)
        save_client(st.session_state.client_data)
        st.success("Client data saved.")


def page_gap_assessment() -> None:
    if not _require_client():
        return

    st.title("Gap Assessment")
    cd = st.session_state.client_data
    _collect_widgets_into_client(cd)
    overall = score_overall(cd)

    # ── Overall maturity gauge ───────────────────────────────────────────────
    pct = overall["overall_pct"]
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number={"suffix": "%", "font": {"size": 40}},
        title={"text": f"Overall Readiness<br><b>{overall['maturity_label']}</b>",
               "font": {"size": 15}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": "#3B82F6"},
            "steps": [
                {"range": [0, 20], "color": "#FEE2E2"},
                {"range": [20, 40], "color": "#FFEDD5"},
                {"range": [40, 60], "color": "#FEF3C7"},
                {"range": [60, 80], "color": "#ECFCCB"},
                {"range": [80, 100], "color": "#DCFCE7"},
            ],
            "threshold": {"line": {"color": "#1E3A8A", "width": 3}, "value": pct},
        },
    ))
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20),
                      paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)

    # ── Pillar summary table ─────────────────────────────────────────────────
    st.markdown("### Pillar Scores")
    rows = []
    for pillar_name, ps in overall["pillars"].items():
        not_met = ps["req_count"] - ps["met_count"] - ps["partial_count"]
        rows.append({
            "Pillar": pillar_name,
            "Score": f"{ps['score']}/{ps['max_score']}",
            "Readiness (%)": ps["percentage"],
            "Maturity": ps["maturity_label"],
            "Met": ps["met_count"],
            "Partial": ps["partial_count"],
            "Not Met / N/A": not_met,
        })
    df = pd.DataFrame(rows)

    def _color_maturity(val):
        colors_map = {
            "Advanced": "background-color:#DCFCE7;color:#15803D",
            "Developing": "background-color:#ECFCCB;color:#65A30D",
            "Emerging": "background-color:#FEF3C7;color:#D97706",
            "Initial": "background-color:#FFEDD5;color:#EA580C",
            "Not Started": "background-color:#FEE2E2;color:#DC2626",
        }
        return colors_map.get(val, "")

    styled = (
        df.style
        .applymap(_color_maturity, subset=["Maturity"])
        .bar(subset=["Readiness (%)"], color="#BFDBFE", vmin=0, vmax=100)
        .format({"Readiness (%)": "{:.1f}%"})
        .set_properties(**{"text-align": "left"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Requirements detail table ────────────────────────────────────────────
    st.markdown("### Requirements Detail")
    detail_rows = []
    for pillar_name in FRAMEWORK:
        pillar_key = PILLAR_DATA_KEYS[pillar_name]
        pillar_data = cd.get(pillar_key, {})
        for req in FRAMEWORK[pillar_name]["requirements"]:
            rid = req["id"]
            req_d = pillar_data.get(rid, {})
            status = req_d.get("status", "")
            detail_rows.append({
                "ID": rid,
                "Ref": req["ref"],
                "Requirement": req["title"],
                "Pillar": pillar_name,
                "Status": STATUS_LABELS.get(status, "Not Assessed"),
                "Notes": req_d.get("notes", ""),
            })

    df2 = pd.DataFrame(detail_rows)

    def _color_status(val):
        rev = {v: k for k, v in STATUS_LABELS.items()}
        key = rev.get(val, "")
        return {
            "met": "background-color:#DCFCE7;color:#15803D",
            "partial": "background-color:#FEF3C7;color:#D97706",
            "not_met": "background-color:#FEE2E2;color:#DC2626",
            "": "background-color:#F3F4F6;color:#6B7280",
        }.get(key, "")

    styled2 = (
        df2.style
        .applymap(_color_status, subset=["Status"])
        .set_properties(**{"text-align": "left"})
    )
    st.dataframe(styled2, use_container_width=True, hide_index=True)

    # ── Priority gaps ────────────────────────────────────────────────────────
    if overall["priority_gaps"]:
        st.markdown("### Priority Gaps (Remediation Roadmap)")
        gap_rows = []
        for i, g in enumerate(overall["priority_gaps"], 1):
            gap_rows.append({
                "Priority": i,
                "ID": g["id"],
                "Requirement": g["title"],
                "Status": STATUS_LABELS.get(g["status"], "Not Assessed"),
                "Notes": g.get("notes", ""),
            })
        df3 = pd.DataFrame(gap_rows)
        styled3 = (
            df3.style
            .applymap(_color_status, subset=["Status"])
            .set_properties(**{"text-align": "left"})
        )
        st.dataframe(styled3, use_container_width=True, hide_index=True)


def page_disclosure_drafts() -> None:
    if not _require_client():
        return

    st.title("Disclosure Drafts")
    st.markdown(
        "The following draft disclosure text is generated from your entered data. "
        "Review, refine and approve each section before inclusion in annual reports "
        "or sustainability disclosures."
    )

    cd = st.session_state.client_data
    _collect_widgets_into_client(cd)

    pillar_tab_names = [f"{PILLAR_ICONS[p]} {p}" for p in FRAMEWORK]
    tabs = st.tabs(pillar_tab_names)

    for tab, pillar_name in zip(tabs, FRAMEWORK):
        with tab:
            disclosures = generate_pillar_disclosures(cd, pillar_name)
            for disc in disclosures:
                st.markdown(
                    f"**{disc['id']}  {disc['title']}**  "
                    f"<small style='color:#64748B'>({disc['ref']})</small>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="disc-box">{disc["text"]}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("")


def page_export() -> None:
    if not _require_client():
        return

    st.title("Export")
    cd = st.session_state.client_data
    _collect_widgets_into_client(cd)
    overall = score_overall(cd)

    st.markdown(f"**Client:** {cd['client_name']}  |  **Period:** {cd.get('reporting_period','')}")
    st.markdown(
        f"Overall readiness: **{overall['overall_pct']:.0f}%** – *{overall['maturity_label']}*"
    )
    st.markdown("---")

    st.markdown("### PDF Report")
    st.markdown(
        "The PDF report includes:  \n"
        "- Cover page and executive summary  \n"
        "- Pillar-by-pillar gap assessment table  \n"
        "- All draft disclosure text  \n"
        "- Prioritised remediation roadmap"
    )

    if st.button("Generate PDF Report", type="primary"):
        with st.spinner("Generating PDF…"):
            try:
                pdf_bytes = generate_pdf(cd)
                safe_name = cd["client_name"].replace(" ", "_")
                period = cd.get("reporting_period", "").replace(" ", "_")
                filename = f"AASB_S2_{safe_name}_{period}.pdf"
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                )
                st.success("PDF generated successfully.")
            except Exception as exc:
                st.error(f"PDF generation failed: {exc}")
                raise

    st.markdown("---")
    st.markdown("### Raw Data Export (JSON)")
    st.download_button(
        label="Download client JSON",
        data=__import__("json").dumps(cd, indent=2, ensure_ascii=False),
        file_name=f"{cd['client_name']}.json",
        mime="application/json",
    )


# ── Carbon Market Registry page ────────────────────────────────────────────────

def _source_badge(source: str) -> str:
    colours = {
        "live": ("#D1FAE5", "#065F46", "Live from CER"),
        "cache": ("#DBEAFE", "#1E40AF", "Cached"),
        "upload": ("#EDE9FE", "#5B21B6", "Uploaded"),
        "sample": ("#FEF3C7", "#92400E", "Demo data"),
    }
    bg, fg, label = colours.get(source, ("#F3F4F6", "#374151", source))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 10px;'
        f'border-radius:12px;font-size:0.78rem;font-weight:600">{label}</span>'
    )


def _fmt_number(n: int | float) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}k"
    return str(int(n))


def page_carbon_registry() -> None:
    st.title("🌿 Carbon Market Registry")
    st.markdown(
        "Explore ACCU scheme projects, project developers, and credit "
        "retirements using data from the **Clean Energy Regulator (CER)**."
    )

    # ── Data source controls ──────────────────────────────────────────────────
    with st.expander("⬇️  Data Sources & Upload", expanded=False):
        st.markdown(
            "The CER publishes project and compliance data publicly. "
            "Click **Refresh from CER** to attempt a live download, or upload "
            "files you have already downloaded from cer.gov.au."
        )
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("**ACCU Project Register**")
            info = DOWNLOAD_INSTRUCTIONS["Project Register"]
            st.markdown(f"[Open CER page]({info['url']})")
            for step in info["steps"]:
                st.caption(f"• {step}")
            proj_upload = st.file_uploader(
                "Upload project register (CSV / XLSX)",
                type=["csv", "xlsx"],
                key="proj_upload",
            )
        with col_b:
            st.markdown("**Safeguard Compliance Data**")
            info2 = DOWNLOAD_INSTRUCTIONS["Safeguard Data"]
            st.markdown(f"[Open CER page]({info2['url']})")
            for step in info2["steps"]:
                st.caption(f"• {step}")
            sg_upload = st.file_uploader(
                "Upload safeguard data (CSV / XLSX)",
                type=["csv", "xlsx"],
                key="sg_upload",
            )
        with col_c:
            st.markdown("**Contract Register**")
            info3 = DOWNLOAD_INSTRUCTIONS["Contract Register"]
            st.markdown(f"[Open CER page]({info3['url']})")
            for step in info3["steps"]:
                st.caption(f"• {step}")
            contract_upload = st.file_uploader(
                "Upload contract register (CSV / XLSX)",
                type=["csv", "xlsx"],
                key="contract_upload",
            )

        force_dl = st.button("🔄 Refresh from CER", type="secondary")

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner("Loading registry data…"):
        proj_df, proj_src = load_project_register(proj_upload, force_download=force_dl)
        sg_df, sg_src = load_safeguard_data(sg_upload, force_download=force_dl)
        contract_df, contract_src = load_contract_register(contract_upload, force_download=force_dl)

    # ── Source indicators ─────────────────────────────────────────────────────
    src_cols = st.columns(3)
    with src_cols[0]:
        st.markdown(
            f"Project Register {_source_badge(proj_src)}",
            unsafe_allow_html=True,
        )
    with src_cols[1]:
        st.markdown(
            f"Safeguard Data {_source_badge(sg_src)}",
            unsafe_allow_html=True,
        )
    with src_cols[2]:
        st.markdown(
            f"Contract Register {_source_badge(contract_src)}",
            unsafe_allow_html=True,
        )

    if any(s == "sample" for s in (proj_src, sg_src, contract_src)):
        st.info(
            "**Demo mode** – showing sample data. Upload CER files or click "
            "**Refresh from CER** above to use live data.",
            icon="ℹ️",
        )

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_overview, tab_projects, tab_devs, tab_retirements = st.tabs([
        "📊 Overview",
        "📋 Project Register",
        "🏗️ Project Developers",
        "♻️ Credit Retirements",
    ])

    # ── Overview tab ──────────────────────────────────────────────────────────
    with tab_overview:
        active = proj_df[proj_df.get("Project Status", proj_df.columns[0]).name == "Project Status"]
        try:
            n_active = int((proj_df["Project Status"] == "Active").sum())
        except Exception:
            n_active = len(proj_df)
        n_total = len(proj_df)
        total_accus = int(proj_df["ACCUs Issued"].sum()) if "ACCUs Issued" in proj_df.columns else 0
        n_devs = proj_df["Project Proponent"].nunique() if "Project Proponent" in proj_df.columns else 0
        total_surrendered = int(sg_df["Total Credits Surrendered"].sum()) if "Total Credits Surrendered" in sg_df.columns else 0
        n_facilities = len(sg_df)

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Projects", f"{n_total:,}")
        m2.metric("Active Projects", f"{n_active:,}")
        m3.metric("ACCUs Issued", _fmt_number(total_accus))
        m4.metric("Project Developers", f"{n_devs:,}")
        m5.metric("Safeguard Facilities", f"{n_facilities:,}")
        m6.metric("Credits Surrendered", _fmt_number(total_surrendered))

        st.markdown("---")
        col_left, col_right = st.columns(2)

        # Projects by method type
        with col_left:
            st.markdown("#### Projects by Method Type")
            if "Method Type" in proj_df.columns:
                method_counts = proj_df["Method Type"].value_counts().reset_index()
                method_counts.columns = ["Method Type", "Projects"]
                fig_mt = go.Figure(go.Bar(
                    x=method_counts["Projects"],
                    y=method_counts["Method Type"],
                    orientation="h",
                    marker_color=["#10B981", "#3B82F6"],
                    text=method_counts["Projects"],
                    textposition="outside",
                ))
                fig_mt.update_layout(
                    margin=dict(l=10, r=30, t=10, b=10),
                    height=220,
                    xaxis_title="Number of Projects",
                    yaxis_title="",
                    plot_bgcolor="white",
                )
                st.plotly_chart(fig_mt, use_container_width=True)

        # Projects by state
        with col_right:
            st.markdown("#### Projects by State")
            if "Project location (State)" in proj_df.columns:
                state_counts = proj_df["Project location (State)"].value_counts().reset_index()
                state_counts.columns = ["State", "Projects"]
                fig_st = go.Figure(go.Bar(
                    x=state_counts["State"],
                    y=state_counts["Projects"],
                    marker_color="#6366F1",
                    text=state_counts["Projects"],
                    textposition="outside",
                ))
                fig_st.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=220,
                    yaxis_title="Projects",
                    plot_bgcolor="white",
                )
                st.plotly_chart(fig_st, use_container_width=True)

        st.markdown("#### Top 10 Methods by ACCUs Issued")
        if "Method" in proj_df.columns and "ACCUs Issued" in proj_df.columns:
            method_accus = (
                proj_df.groupby("Method")["ACCUs Issued"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            fig_ma = go.Figure(go.Bar(
                x=method_accus["ACCUs Issued"],
                y=method_accus["Method"],
                orientation="h",
                marker_color="#0EA5E9",
                text=[_fmt_number(v) for v in method_accus["ACCUs Issued"]],
                textposition="outside",
            ))
            fig_ma.update_layout(
                margin=dict(l=10, r=60, t=10, b=10),
                height=350,
                xaxis_title="ACCUs Issued",
                yaxis_title="",
                plot_bgcolor="white",
            )
            st.plotly_chart(fig_ma, use_container_width=True)

    # ── Project Register tab ──────────────────────────────────────────────────
    with tab_projects:
        st.markdown("#### ACCU Scheme Project Register")
        st.caption(
            "Full list of all registered ACCU scheme projects. "
            "Use the filters to narrow results."
        )

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            all_states = sorted(proj_df["Project location (State)"].dropna().unique().tolist()) \
                if "Project location (State)" in proj_df.columns else []
            sel_states = st.multiselect("State/Territory", all_states, key="proj_state_filter")
        with fc2:
            all_methods = sorted(proj_df["Method"].dropna().unique().tolist()) \
                if "Method" in proj_df.columns else []
            sel_methods = st.multiselect("Method", all_methods, key="proj_method_filter")
        with fc3:
            status_opts = ["All", "Active", "Revoked"]
            sel_status = st.selectbox("Status", status_opts, key="proj_status_filter")

        filtered = proj_df.copy()
        if sel_states:
            filtered = filtered[filtered["Project location (State)"].isin(sel_states)]
        if sel_methods:
            filtered = filtered[filtered["Method"].isin(sel_methods)]
        if sel_status != "All":
            filtered = filtered[filtered["Project Status"] == sel_status]

        st.caption(f"Showing {len(filtered):,} of {len(proj_df):,} projects")

        display_cols = [c for c in [
            "Project ID", "Project Name", "Project Proponent", "Method",
            "Method Type", "Project location (State)", "Project Status",
            "ACCUs Issued", "Date Project Registered",
        ] if c in filtered.columns]
        st.dataframe(filtered[display_cols], use_container_width=True, height=450)

        st.download_button(
            "⬇️ Download filtered data (CSV)",
            data=filtered[display_cols].to_csv(index=False),
            file_name="accu_project_register.csv",
            mime="text/csv",
        )

    # ── Project Developers tab ────────────────────────────────────────────────
    with tab_devs:
        st.markdown("#### Project Developer Profiles")
        st.caption(
            "Aggregated view of each organisation operating as a project "
            "proponent (developer) in the ACCU Scheme."
        )

        dev_df = summarise_developers(proj_df)

        # Top developers chart
        top_n = min(15, len(dev_df))
        top_devs = dev_df.head(top_n)
        fig_devs = go.Figure()
        fig_devs.add_trace(go.Bar(
            y=top_devs["Developer"],
            x=top_devs["ACCUs Issued"],
            name="ACCUs Issued",
            orientation="h",
            marker_color="#10B981",
            text=[_fmt_number(v) for v in top_devs["ACCUs Issued"]],
            textposition="outside",
        ))
        fig_devs.update_layout(
            title=f"Top {top_n} Developers by ACCUs Issued",
            margin=dict(l=10, r=80, t=40, b=10),
            height=max(300, top_n * 30),
            xaxis_title="ACCUs Issued",
            yaxis=dict(autorange="reversed"),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig_devs, use_container_width=True)

        # Developer search
        dev_search = st.text_input("Search developer", placeholder="Type to filter…", key="dev_search")
        dev_view = dev_df.copy()
        if dev_search:
            dev_view = dev_view[
                dev_view["Developer"].str.contains(dev_search, case=False, na=False)
            ]

        st.dataframe(dev_view, use_container_width=True, height=380)

        # Developer drill-down
        st.markdown("---")
        st.markdown("#### Developer Drill-down")
        chosen_dev = st.selectbox(
            "Select a developer",
            options=["— select —"] + dev_df["Developer"].tolist(),
            key="dev_drilldown",
        )
        if chosen_dev != "— select —":
            dev_projects = proj_df[proj_df["Project Proponent"] == chosen_dev]
            d_cols = [c for c in [
                "Project ID", "Project Name", "Method", "Method Type",
                "Project location (State)", "Project Status",
                "ACCUs Issued", "Date Project Registered",
            ] if c in dev_projects.columns]

            d1, d2, d3 = st.columns(3)
            d1.metric("Total Projects", len(dev_projects))
            d2.metric("Active Projects", int((dev_projects.get("Project Status", pd.Series()) == "Active").sum()))
            d3.metric("ACCUs Issued", _fmt_number(int(dev_projects["ACCUs Issued"].sum())))

            st.dataframe(dev_projects[d_cols], use_container_width=True, height=300)

            # Check for matching contracts
            if "Project Proponent" in contract_df.columns:
                dev_contracts = contract_df[contract_df["Project Proponent"] == chosen_dev]
                if not dev_contracts.empty:
                    st.markdown("**Government contracts (ERF auction)**")
                    st.dataframe(dev_contracts, use_container_width=True)

        st.download_button(
            "⬇️ Download developer summary (CSV)",
            data=dev_df.to_csv(index=False),
            file_name="accu_developer_summary.csv",
            mime="text/csv",
        )

    # ── Credit Retirements tab ────────────────────────────────────────────────
    with tab_retirements:
        st.markdown("#### Credit Retirements – Safeguard Mechanism Compliance")
        st.caption(
            "Safeguard Mechanism covered facilities and their ACCU / SMC "
            "surrenders to meet compliance obligations."
        )

        # KPIs
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Facilities", f"{len(sg_df):,}")
        r2.metric(
            "Total Covered Emissions",
            _fmt_number(int(sg_df["Covered Emissions (tCO2e)"].sum())) + " tCO2e"
            if "Covered Emissions (tCO2e)" in sg_df.columns else "—",
        )
        r3.metric(
            "ACCUs Surrendered",
            _fmt_number(int(sg_df["ACCUs Surrendered"].sum()))
            if "ACCUs Surrendered" in sg_df.columns else "—",
        )
        r4.metric(
            "SMCs Surrendered",
            _fmt_number(int(sg_df["SMCs Surrendered"].sum()))
            if "SMCs Surrendered" in sg_df.columns else "—",
        )

        st.markdown("---")
        col_l, col_r = st.columns(2)

        # Surrenders by sector
        with col_l:
            st.markdown("#### Credits Surrendered by Sector")
            if "Industry Sector" in sg_df.columns and "Total Credits Surrendered" in sg_df.columns:
                sec_data = (
                    sg_df.groupby("Industry Sector")["Total Credits Surrendered"]
                    .sum()
                    .sort_values(ascending=False)
                    .reset_index()
                )
                fig_sec = go.Figure(go.Bar(
                    y=sec_data["Industry Sector"],
                    x=sec_data["Total Credits Surrendered"],
                    orientation="h",
                    marker_color="#F59E0B",
                    text=[_fmt_number(v) for v in sec_data["Total Credits Surrendered"]],
                    textposition="outside",
                ))
                fig_sec.update_layout(
                    margin=dict(l=10, r=60, t=10, b=10),
                    height=350,
                    xaxis_title="Credits Surrendered",
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor="white",
                )
                st.plotly_chart(fig_sec, use_container_width=True)

        # ACCU vs SMC breakdown
        with col_r:
            st.markdown("#### ACCU vs SMC Split by Sector")
            if all(c in sg_df.columns for c in ["Industry Sector", "ACCUs Surrendered", "SMCs Surrendered"]):
                sec_split = sg_df.groupby("Industry Sector")[
                    ["ACCUs Surrendered", "SMCs Surrendered"]
                ].sum().sort_values("ACCUs Surrendered", ascending=False).head(8).reset_index()

                fig_split = go.Figure()
                fig_split.add_trace(go.Bar(
                    name="ACCUs",
                    y=sec_split["Industry Sector"],
                    x=sec_split["ACCUs Surrendered"],
                    orientation="h",
                    marker_color="#3B82F6",
                ))
                fig_split.add_trace(go.Bar(
                    name="SMCs",
                    y=sec_split["Industry Sector"],
                    x=sec_split["SMCs Surrendered"],
                    orientation="h",
                    marker_color="#8B5CF6",
                ))
                fig_split.update_layout(
                    barmode="stack",
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=350,
                    xaxis_title="Credits",
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor="white",
                    legend=dict(orientation="h", y=1.05),
                )
                st.plotly_chart(fig_split, use_container_width=True)

        # Sector summary table
        st.markdown("#### Sector Summary")
        sector_summary = summarise_retirements(sg_df)
        st.dataframe(sector_summary, use_container_width=True)

        # Facility-level table
        st.markdown("---")
        st.markdown("#### Facility-Level Data")
        rf1, rf2 = st.columns(2)
        with rf1:
            all_sectors = sorted(sg_df["Industry Sector"].dropna().unique().tolist()) \
                if "Industry Sector" in sg_df.columns else []
            sel_sectors = st.multiselect("Filter by sector", all_sectors, key="sg_sector_filter")
        with rf2:
            all_sg_states = sorted(sg_df["State/Territory"].dropna().unique().tolist()) \
                if "State/Territory" in sg_df.columns else []
            sel_sg_states = st.multiselect("Filter by state", all_sg_states, key="sg_state_filter")

        sg_filtered = sg_df.copy()
        if sel_sectors:
            sg_filtered = sg_filtered[sg_filtered["Industry Sector"].isin(sel_sectors)]
        if sel_sg_states:
            sg_filtered = sg_filtered[sg_filtered["State/Territory"].isin(sel_sg_states)]

        sg_display_cols = [c for c in [
            "Facility Name", "State/Territory", "Industry Sector",
            "Covered Emissions (tCO2e)", "Baseline Emissions (tCO2e)",
            "Net Position (tCO2e)", "ACCUs Surrendered", "SMCs Surrendered",
            "Total Credits Surrendered", "Compliance Status",
        ] if c in sg_filtered.columns]

        st.dataframe(sg_filtered[sg_display_cols], use_container_width=True, height=420)

        st.download_button(
            "⬇️ Download safeguard data (CSV)",
            data=sg_filtered[sg_display_cols].to_csv(index=False),
            file_name="safeguard_compliance.csv",
            mime="text/csv",
        )


# ── Router ─────────────────────────────────────────────────────────────────────
page = st.session_state.page

if page == "Overview":
    page_overview()
elif page in ("Governance", "Strategy", "Risk Management", "Metrics & Targets"):
    page_pillar_form(page)
elif page == "Gap Assessment":
    page_gap_assessment()
elif page == "Disclosure Drafts":
    page_disclosure_drafts()
elif page == "Export":
    page_export()
elif page == "Carbon Market Registry":
    page_carbon_registry()
