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
from modules import accu_methods
from modules.pptx_export import build_pptx

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
    "ACCU Methods": "🌱",
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
    "ACCU Methods",
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


def page_accu_methods() -> None:
    st.title("🌱 ACCU Methods Overview")
    st.caption(
        "Australian Carbon Credit Unit (ACCU) methods grouped by category, "
        "with status (Active, Next to Close, Under Development) for each. "
        "Edit inline and export to a Pollination-style PowerPoint slide."
    )

    if "accu_data" not in st.session_state:
        st.session_state.accu_data = accu_methods.load_data()

    data = st.session_state.accu_data

    # ── Headline + insights editors ─────────────────────────────────────────
    with st.expander("Slide headline & key insights", expanded=False):
        data["eyebrow"] = st.text_input("Eyebrow", value=data.get("eyebrow", ""))
        data["headline"] = st.text_area(
            "Headline", value=data.get("headline", ""), height=70,
        )
        insights_text = st.text_area(
            "Key insights (one bullet per line)",
            value="\n\n".join(data.get("key_insights", [])),
            height=180,
        )
        data["key_insights"] = [
            line.strip() for line in insights_text.split("\n\n") if line.strip()
        ]
        data["footnote"] = st.text_area(
            "Footnote", value=data.get("footnote", ""), height=70,
        )
        sources_text = st.text_area(
            "Sources (one per line)",
            value="\n".join(data.get("sources", [])),
            height=100,
        )
        data["sources"] = [s.strip() for s in sources_text.split("\n") if s.strip()]

    # ── KPI row ─────────────────────────────────────────────────────────────
    counts = accu_methods.status_counts(data)
    kpi = st.columns(4)
    kpi[0].metric("Total methods", len(data["methods"]))
    kpi[1].metric("Active", counts["active"])
    kpi[2].metric("Next to Close", counts["next_to_close"])
    kpi[3].metric("Under Development", counts["under_development"])

    # ── Audit panel ─────────────────────────────────────────────────────────
    findings = accu_methods.audit_data(data)
    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 99))
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    infos = sum(1 for f in findings if f["severity"] == "info")
    if findings:
        audit_label = (
            f"🔍 Data audit — {errors} error(s), {warnings} warning(s), "
            f"{infos} info"
        )
    else:
        audit_label = "🔍 Data audit — no issues found"
    with st.expander(audit_label, expanded=bool(errors or warnings)):
        st.caption(
            "Internal consistency checks against the methods table and the "
            "narrative insights. Not a substitute for source verification "
            "against DCCEEW publications."
        )
        if not findings:
            st.success("All internal checks pass.")
        else:
            badge = {
                "error": ("🔴", "#FEE2E2", "#991B1B"),
                "warning": ("🟠", "#FEF3C7", "#92400E"),
                "info": ("🔵", "#DBEAFE", "#1E40AF"),
            }
            for f in findings:
                icon, bg, fg = badge[f["severity"]]
                st.markdown(
                    f'<div style="background:{bg};color:{fg};padding:8px 12px;'
                    f'border-radius:6px;margin-bottom:6px;font-size:0.88rem;">'
                    f'{icon} <strong>{f["severity"].upper()}</strong> '
                    f'<code style="background:transparent;color:{fg};">'
                    f'{f["code"]}</code> — {f["message"]}</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── Editable methods table (data_editor) ────────────────────────────────
    st.markdown("### Methods")
    df = pd.DataFrame(data["methods"])
    if df.empty:
        df = pd.DataFrame(columns=accu_methods.COLUMNS)
    # ensure all expected columns exist
    for c in accu_methods.COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[accu_methods.COLUMNS]

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "methodology": st.column_config.TextColumn("Methodology", width="large"),
            "category": st.column_config.SelectboxColumn(
                "Category", options=accu_methods.CATEGORIES, required=True,
            ),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=accu_methods.STATUSES,
                required=True,
                help="active / next_to_close / under_development",
            ),
            "status_timing": st.column_config.TextColumn("Status / Timing"),
            "updates": st.column_config.TextColumn("Updates", width="medium"),
        },
        key="accu_methods_editor",
    )
    data["methods"] = edited.to_dict(orient="records")

    # ── Grouped preview by category ─────────────────────────────────────────
    st.markdown("### Preview – grouped by category")
    grouped = accu_methods.methods_by_category(data)
    for cat in accu_methods.CATEGORIES:
        rows = grouped[cat]
        if not rows:
            continue
        color = accu_methods.CATEGORY_COLORS[cat]
        st.markdown(
            f'<div style="background:{color};color:white;padding:6px 12px;'
            f'border-radius:4px;font-weight:600;font-size:0.9rem;'
            f'margin-top:0.6rem;">{cat.upper()} '
            f'<span style="opacity:0.8;font-weight:400;">'
            f'({len(rows)} methods)</span></div>',
            unsafe_allow_html=True,
        )
        prev = pd.DataFrame(rows)[
            ["methodology", "status", "status_timing", "updates"]
        ].copy()
        prev["status"] = prev["status"].map(
            lambda s: accu_methods.STATUS_LABELS.get(s, s)
        )
        prev.columns = ["Methodology", "Status", "Timing", "Updates"]
        st.dataframe(prev, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Action buttons ──────────────────────────────────────────────────────
    btns = st.columns(4)
    with btns[0]:
        if st.button("💾 Save", use_container_width=True, type="primary"):
            accu_methods.save_data(data)
            st.success("ACCU methods data saved.")
    with btns[1]:
        if st.button("↺ Reset to defaults", use_container_width=True):
            st.session_state.accu_data = accu_methods.reset_data()
            st.rerun()
    with btns[2]:
        if st.button("📤 Build slide", use_container_width=True):
            st.session_state.accu_pptx_bytes = build_pptx(data)
            st.success("Slide built – download below.")
    with btns[3]:
        st.download_button(
            label="⬇️  Methods CSV",
            data=accu_methods.methods_to_csv(data),
            file_name="accu_methods.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if st.session_state.get("accu_pptx_bytes"):
        st.download_button(
            label="⬇️  Download Pollination slide (.pptx)",
            data=st.session_state.accu_pptx_bytes,
            file_name="ACCU_Methods_Overview.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            type="primary",
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
elif page == "ACCU Methods":
    page_accu_methods()
