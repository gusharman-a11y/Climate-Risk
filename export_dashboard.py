"""
Generate a fully self-contained HTML carbon market dashboard.
Run:  python export_dashboard.py
Opens (or saves) carbon_market_dashboard.html
"""
import json
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from modules.carbon_data import get_projects_df, get_issuances_df, PROJECTS

projects_df = get_projects_df()
issuances_df = get_issuances_df()

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
STATUS_COLOURS = {
    "Active":           "#15803D",
    "Retired":          "#475569",
    "Under Validation": "#D97706",
    "Suspended":        "#DC2626",
}

# ── Chart builders ─────────────────────────────────────────────────────────────

def chart_annual_trend(isf):
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
        title="Annual Credit Issuances vs Retirements",
        barmode="group",
        xaxis=dict(title="Vintage Year", tickmode="linear", dtick=1),
        yaxis=dict(title="tCO₂e", tickformat=",.0f", gridcolor="#F1F5F9"),
        plot_bgcolor="white", paper_bgcolor="white",
        height=380,
        legend=dict(orientation="h", y=1.08),
        font=dict(family="Inter, Helvetica, sans-serif", size=13),
        margin=dict(l=60, r=20, t=60, b=60),
    )
    return fig


def chart_by_type(isf):
    by_type = (
        isf.groupby("type")["credits_issued"].sum()
        .sort_values(ascending=True)
        .reset_index()
    )
    colours = [TYPE_COLOURS.get(t, "#94A3B8") for t in by_type["type"]]
    fig = go.Figure(go.Bar(
        x=by_type["credits_issued"], y=by_type["type"],
        orientation="h",
        marker_color=colours,
        hovertemplate="%{y}<br>%{x:,.0f} tCO₂e<extra></extra>",
        text=[f"{v/1e6:.2f} M" for v in by_type["credits_issued"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Credits Issued by Project Type",
        xaxis=dict(tickformat=",.0f", gridcolor="#F1F5F9"),
        plot_bgcolor="white", paper_bgcolor="white",
        height=360,
        font=dict(family="Inter, Helvetica, sans-serif", size=13),
        margin=dict(l=140, r=80, t=60, b=40),
    )
    return fig


def chart_by_standard(isf):
    by_std = (
        isf.groupby("standard")["credits_issued"].sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    std_colours = [STANDARD_COLOURS.get(s, "#94A3B8") for s in by_std["standard"]]
    fig = go.Figure(go.Pie(
        labels=by_std["standard"],
        values=by_std["credits_issued"],
        marker_colors=std_colours,
        hole=0.45,
        hovertemplate="%{label}<br>%{value:,.0f} tCO₂e (%{percent})<extra></extra>",
        textinfo="label+percent",
        textfont_size=13,
    ))
    fig.update_layout(
        title="Credits Issued by Standard",
        height=360,
        paper_bgcolor="white",
        showlegend=False,
        font=dict(family="Inter, Helvetica, sans-serif", size=13),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


def chart_by_country(isf):
    by_country = (
        isf.groupby("country")["credits_issued"].sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    fig = go.Figure(go.Bar(
        x=by_country["country"], y=by_country["credits_issued"],
        marker_color="#6366F1",
        hovertemplate="%{x}<br>%{y:,.0f} tCO₂e<extra></extra>",
        text=[f"{v/1e6:.2f} M" for v in by_country["credits_issued"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Credits Issued by Country",
        yaxis=dict(tickformat=",.0f", gridcolor="#F1F5F9"),
        plot_bgcolor="white", paper_bgcolor="white",
        height=380,
        font=dict(family="Inter, Helvetica, sans-serif", size=13),
        margin=dict(l=60, r=20, t=60, b=60),
    )
    return fig


def chart_retirement_rate(isf):
    type_agg = (
        isf.groupby("type")
        .agg(issued=("credits_issued", "sum"), retired=("credits_retired", "sum"))
        .reset_index()
    )
    type_agg["rate"] = (type_agg["retired"] / type_agg["issued"] * 100).round(1)
    type_agg = type_agg.sort_values("rate", ascending=False)
    colours = [TYPE_COLOURS.get(t, "#94A3B8") for t in type_agg["type"]]
    fig = go.Figure(go.Bar(
        x=type_agg["type"], y=type_agg["rate"],
        marker_color=colours,
        hovertemplate="%{x}<br>Retirement rate: %{y:.1f}%<extra></extra>",
        text=[f"{v:.1f}%" for v in type_agg["rate"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="Retirement Rate by Project Type",
        yaxis=dict(range=[0, 115], ticksuffix="%", gridcolor="#F1F5F9"),
        plot_bgcolor="white", paper_bgcolor="white",
        height=360,
        font=dict(family="Inter, Helvetica, sans-serif", size=13),
        margin=dict(l=60, r=20, t=60, b=60),
    )
    return fig


def chart_stacked_area(isf):
    pivot = (
        isf.groupby(["vintage_year", "type"])["credits_issued"]
        .sum().reset_index()
    )
    types_ordered = (
        pivot.groupby("type")["credits_issued"].sum()
        .sort_values(ascending=False).index.tolist()
    )
    fig = go.Figure()
    for ptype in types_ordered:
        sub = pivot[pivot["type"] == ptype].sort_values("vintage_year")
        fig.add_trace(go.Scatter(
            x=sub["vintage_year"], y=sub["credits_issued"],
            mode="lines+markers", name=ptype,
            stackgroup="one",
            line=dict(color=TYPE_COLOURS.get(ptype, "#94A3B8"), width=2),
            hovertemplate=f"{ptype}<br>Vintage %{{x}}<br>%{{y:,.0f}} tCO₂e<extra></extra>",
        ))
    fig.update_layout(
        title="Cumulative Issuances by Type Over Time",
        xaxis=dict(title="Vintage Year", tickmode="linear", dtick=1),
        yaxis=dict(title="tCO₂e", tickformat=",.0f", gridcolor="#F1F5F9"),
        plot_bgcolor="white", paper_bgcolor="white",
        height=400,
        legend=dict(orientation="h", y=-0.22),
        font=dict(family="Inter, Helvetica, sans-serif", size=13),
        margin=dict(l=60, r=20, t=60, b=100),
    )
    return fig


# ── Project table HTML ─────────────────────────────────────────────────────────

def projects_table_html(pf):
    status_badge = {
        "Active":           ("background:#DCFCE7;color:#15803D", "Active"),
        "Retired":          ("background:#F1F5F9;color:#475569", "Retired"),
        "Under Validation": ("background:#FEF3C7;color:#D97706", "Under Validation"),
        "Suspended":        ("background:#FEE2E2;color:#DC2626", "Suspended"),
    }
    rows = ""
    for _, r in pf.iterrows():
        style, label = status_badge.get(r["status"], ("background:#F3F4F6;color:#6B7280", r["status"]))
        area = f"{r['area_ha']:,.0f} ha" if pd.notna(r["area_ha"]) and r["area_ha"] else "N/A"
        rows += f"""
        <tr>
          <td><strong>{r['id']}</strong><br><small>{r['name']}</small></td>
          <td>{r['type']}</td>
          <td>{r['country']}</td>
          <td>{r['standard']}</td>
          <td><span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;{style}">{label}</span></td>
          <td>{area}</td>
          <td style="text-align:right">{r['vintage_start']}–{r['vintage_end']}</td>
          <td style="text-align:right">{r['total_issued']/1e6:.2f} M</td>
          <td style="text-align:right">{r['total_retired']/1e6:.2f} M</td>
          <td style="text-align:right">{r['credits_outstanding']/1e6:.2f} M</td>
        </tr>"""
    return f"""
    <table id="projects-table" class="data-table">
      <thead>
        <tr>
          <th>Project</th><th>Type</th><th>Country</th><th>Standard</th>
          <th>Status</th><th>Area</th><th>Vintages</th>
          <th>Issued (M tCO₂e)</th><th>Retired (M tCO₂e)</th><th>Outstanding (M tCO₂e)</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def issuances_table_html(isf):
    rows = ""
    sorted_isf = isf.sort_values(["vintage_year", "credits_issued"], ascending=[False, False])
    for _, r in sorted_isf.iterrows():
        rate = r["credits_retired"] / r["credits_issued"] * 100 if r["credits_issued"] else 0
        bar_w = min(int(rate), 100)
        rows += f"""
        <tr>
          <td><strong>{r['project_id']}</strong><br><small>{r['project_name']}</small></td>
          <td>{r['vintage_year']}</td>
          <td>{r['type']}</td>
          <td>{r['country']}</td>
          <td>{r['standard']}</td>
          <td style="text-align:right">{r['credits_issued']:,.0f}</td>
          <td style="text-align:right">{r['credits_retired']:,.0f}</td>
          <td>
            <div style="display:flex;align-items:center;gap:6px">
              <div style="background:#E2E8F0;border-radius:4px;width:80px;height:10px;overflow:hidden">
                <div style="background:#10B981;width:{bar_w}%;height:100%;border-radius:4px"></div>
              </div>
              <span style="font-size:0.8rem">{rate:.1f}%</span>
            </div>
          </td>
        </tr>"""
    return f"""
    <table id="issuances-table" class="data-table">
      <thead>
        <tr>
          <th>Project</th><th>Vintage</th><th>Type</th><th>Country</th>
          <th>Standard</th><th>Issued (tCO₂e)</th><th>Retired (tCO₂e)</th><th>Retirement %</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


# ── Render charts to HTML divs ─────────────────────────────────────────────────

def fig_div(fig, div_id):
    return pio.to_html(fig, full_html=False, include_plotlyjs=False, div_id=div_id)


isf = issuances_df
pf = projects_df

total_issued = isf["credits_issued"].sum()
total_retired = isf["credits_retired"].sum()
outstanding = total_issued - total_retired
active_count = len(pf[pf["status"] == "Active"])
total_projects = len(pf)

chart_trend_html   = fig_div(chart_annual_trend(isf),     "chart-trend")
chart_type_html    = fig_div(chart_by_type(isf),          "chart-type")
chart_std_html     = fig_div(chart_by_standard(isf),      "chart-std")
chart_country_html = fig_div(chart_by_country(isf),       "chart-country")
chart_retire_html  = fig_div(chart_retirement_rate(isf),  "chart-retire")
chart_area_html    = fig_div(chart_stacked_area(isf),     "chart-area")
proj_table         = projects_table_html(pf)
iss_table          = issuances_table_html(isf)

# ── Full HTML page ─────────────────────────────────────────────────────────────

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carbon Market Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Inter, -apple-system, Helvetica, sans-serif; background: #F8FAFC; color: #1E293B; }}
  header {{ background: #0F172A; color: #E2E8F0; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }}
  header h1 {{ font-size: 1.4rem; font-weight: 700; }}
  header span {{ font-size: 0.85rem; color: #94A3B8; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(5,1fr); gap: 1rem; margin-bottom: 2rem; }}
  .kpi {{ background: white; border-radius: 10px; padding: 1.25rem 1.5rem; border: 1px solid #E2E8F0;
           box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  .kpi label {{ font-size: 0.75rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: .05em; }}
  .kpi .value {{ font-size: 1.65rem; font-weight: 700; color: #0F172A; margin-top: .25rem; }}
  .tabs {{ display: flex; gap: .5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #E2E8F0; padding-bottom: 0; }}
  .tab-btn {{ padding: .6rem 1.25rem; border: none; background: none; cursor: pointer;
               font-size: .9rem; font-weight: 600; color: #64748B; border-bottom: 3px solid transparent;
               margin-bottom: -2px; transition: all .15s; }}
  .tab-btn.active {{ color: #1D4ED8; border-bottom-color: #1D4ED8; }}
  .tab-btn:hover {{ color: #1D4ED8; }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .card {{ background: white; border-radius: 10px; border: 1px solid #E2E8F0;
            box-shadow: 0 1px 3px rgba(0,0,0,.06); padding: 1.25rem; margin-bottom: 1.5rem; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }}
  .section-title {{ font-size: 1rem; font-weight: 700; color: #0F172A; margin-bottom: 1rem; }}
  .search-bar {{ width: 100%; padding: .65rem 1rem; border: 1px solid #CBD5E1; border-radius: 8px;
                  font-size: .9rem; margin-bottom: 1.25rem; outline: none; }}
  .search-bar:focus {{ border-color: #3B82F6; box-shadow: 0 0 0 3px rgba(59,130,246,.15); }}
  .data-table {{ width: 100%; border-collapse: collapse; font-size: .84rem; }}
  .data-table th {{ background: #F1F5F9; padding: .65rem .9rem; text-align: left; font-weight: 600;
                     color: #475569; font-size: .75rem; text-transform: uppercase; letter-spacing: .04em;
                     border-bottom: 2px solid #E2E8F0; white-space: nowrap; }}
  .data-table td {{ padding: .6rem .9rem; border-bottom: 1px solid #F1F5F9; vertical-align: middle; }}
  .data-table tr:hover td {{ background: #F8FAFC; }}
  .data-table td small {{ color: #64748B; font-size: .78rem; }}
  .download-btn {{ display: inline-block; margin-top: 1rem; padding: .55rem 1.2rem; background: #1D4ED8;
                    color: white; border-radius: 7px; font-size: .85rem; font-weight: 600;
                    cursor: pointer; border: none; }}
  .download-btn:hover {{ background: #1e40af; }}
  @media(max-width:900px) {{ .kpi-row {{ grid-template-columns: repeat(2,1fr); }} .grid-2 {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header>
  <span style="font-size:1.8rem">🌿</span>
  <div>
    <h1>Carbon Market Dashboard</h1>
    <span>Voluntary &amp; compliance carbon projects · {total_projects} projects · {len(isf)} issuance records</span>
  </div>
</header>

<div class="container">

  <!-- KPIs -->
  <div class="kpi-row">
    <div class="kpi"><label>Total Projects</label><div class="value">{total_projects}</div></div>
    <div class="kpi"><label>Active Projects</label><div class="value">{active_count}</div></div>
    <div class="kpi"><label>Credits Issued</label><div class="value">{total_issued/1e6:.1f} M<span style="font-size:1rem;color:#64748B"> tCO₂e</span></div></div>
    <div class="kpi"><label>Credits Retired</label><div class="value">{total_retired/1e6:.1f} M<span style="font-size:1rem;color:#64748B"> tCO₂e</span></div></div>
    <div class="kpi"><label>Outstanding</label><div class="value">{outstanding/1e6:.1f} M<span style="font-size:1rem;color:#64748B"> tCO₂e</span></div></div>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab-btn active" onclick="showTab('overview',this)">Overview</button>
    <button class="tab-btn" onclick="showTab('projects',this)">Projects</button>
    <button class="tab-btn" onclick="showTab('issuances',this)">Issuances</button>
  </div>

  <!-- Overview tab -->
  <div id="tab-overview" class="tab-panel active">
    <div class="card">{chart_trend_html}</div>
    <div class="grid-2">
      <div class="card">{chart_type_html}</div>
      <div class="card">{chart_std_html}</div>
    </div>
    <div class="card">{chart_country_html}</div>
    <div class="card">{chart_retire_html}</div>
  </div>

  <!-- Projects tab -->
  <div id="tab-projects" class="tab-panel">
    <div class="card">
      <input class="search-bar" id="proj-search" placeholder="Search by name, type, country, standard…" oninput="filterTable('projects-table','proj-search')">
      {proj_table}
    </div>
  </div>

  <!-- Issuances tab -->
  <div id="tab-issuances" class="tab-panel">
    <div class="card">{chart_area_html}</div>
    <div class="card">
      <input class="search-bar" id="iss-search" placeholder="Search by project, type, country…" oninput="filterTable('issuances-table','iss-search')">
      {iss_table}
      <button class="download-btn" onclick="downloadCSV()">Download CSV</button>
    </div>
  </div>

</div><!-- /container -->

<script>
function showTab(name, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
}}

function filterTable(tableId, inputId) {{
  const q = document.getElementById(inputId).value.toLowerCase();
  document.querySelectorAll('#' + tableId + ' tbody tr').forEach(row => {{
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}

function downloadCSV() {{
  const table = document.getElementById('issuances-table');
  const rows = [...table.querySelectorAll('tr')].map(r =>
    [...r.querySelectorAll('th,td')].map(c => '"' + c.innerText.replace(/"/g,'""').replace(/\\n/g,' ') + '"').join(',')
  );
  const blob = new Blob([rows.join('\\n')], {{type:'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'carbon_issuances.csv';
  a.click();
}}
</script>
</body>
</html>"""

out = os.path.join(os.path.dirname(__file__), "carbon_market_dashboard.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"Saved: {out}  ({len(HTML)//1024} KB)")
