"""
Build a self-contained static HTML version of the carbon market dashboard.

Usage:

    python -m tools.build_static_html              # uses cached CER data if present, else sample
    python -m tools.build_static_html -o out.html  # custom output path

The generated file embeds the dataset as JSON, loads Plotly.js from a CDN, and
provides client-side filters and tabs. No Python or server required after build.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules import carbon_market as cm  # noqa: E402


def _to_jsonable(obj):
    if isinstance(obj, (datetime, date)):
        return obj.strftime("%Y-%m-%d")
    raise TypeError(f"not serialisable: {type(obj)}")


def _build_payload() -> dict:
    cm.load_dataset.clear()  # type: ignore[attr-defined]
    projects, issuances = cm.load_dataset()

    p = projects.copy()
    for c in ("registered", "crediting_start"):
        if c in p.columns:
            p[c] = p[c].dt.strftime("%Y-%m-%d").fillna("")

    i = issuances.copy()
    if "issuance_month" in i.columns:
        i["issuance_month"] = i["issuance_month"].dt.strftime("%Y-%m").fillna("")

    from modules import cer_fetch
    reg_path = cer_fetch.cached_register_path()
    source = "Live CER cache" if reg_path else "Illustrative sample data"

    return {
        "source": source,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "projects": p.to_dict(orient="records"),
        "issuances": i.to_dict(orient="records"),
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Carbon Market Dashboard – ACCU scheme</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  :root {
    --bg: #0F172A;
    --card: #FFFFFF;
    --border: #E2E8F0;
    --muted: #64748B;
    --text: #0F172A;
    --accent: #16a34a;
    --accent-soft: #dcfce7;
  }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         color:var(--text); background:#F1F5F9; }
  header { background:var(--bg); color:#fff; padding:18px 28px; }
  header h1 { margin:0; font-size:20px; font-weight:600; }
  header .sub { color:#94A3B8; font-size:13px; margin-top:4px; }
  main { max-width:1280px; margin:0 auto; padding:20px; }
  .banner { background:var(--accent-soft); color:#14532d; border-left:4px solid var(--accent);
            border-radius:6px; padding:10px 14px; margin-bottom:16px; font-size:13px; }
  .filters { background:var(--card); border:1px solid var(--border); border-radius:8px;
             padding:14px; margin-bottom:16px; display:grid;
             grid-template-columns: repeat(4, 1fr); gap:12px; }
  .filters label { display:block; font-size:12px; color:var(--muted); margin-bottom:4px; }
  .filters select, .filters input { width:100%; padding:6px 8px; border:1px solid var(--border);
                                    border-radius:6px; font:inherit; background:#fff; }
  .filters select[multiple] { height:90px; }
  .tabs { display:flex; gap:4px; margin-bottom:12px; border-bottom:1px solid var(--border); }
  .tab { padding:8px 16px; cursor:pointer; border:none; background:transparent;
         font:inherit; color:var(--muted); border-bottom:2px solid transparent; }
  .tab.active { color:var(--text); border-bottom-color:var(--accent); font-weight:600; }
  .tab-panel { display:none; }
  .tab-panel.active { display:block; }
  .metrics { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:16px; }
  .metric { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 14px; }
  .metric .label { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
  .metric .value { font-size:22px; font-weight:600; margin-top:4px; }
  .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:8px; }
  .card-title { font-size:13px; font-weight:600; padding:6px 8px 0 8px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:6px 8px; text-align:left; border-bottom:1px solid var(--border); }
  th { background:#F8FAFC; cursor:pointer; user-select:none; position:sticky; top:0; }
  th .arrow { color:var(--muted); font-size:10px; margin-left:3px; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  .table-wrap { background:var(--card); border:1px solid var(--border); border-radius:8px;
                max-height:520px; overflow:auto; }
  .row-actions { display:flex; gap:8px; align-items:center; margin:8px 0 12px; }
  .row-actions input[type=text] { flex:1; padding:6px 10px; border:1px solid var(--border);
                                   border-radius:6px; font:inherit; }
  .btn { padding:6px 12px; border:1px solid var(--border); background:#fff; border-radius:6px;
         cursor:pointer; font:inherit; }
  .btn:hover { background:#F1F5F9; }
  .small { font-size:12px; color:var(--muted); }
  .pill { display:inline-block; padding:1px 8px; border-radius:10px; font-size:11px;
          background:#F1F5F9; color:#475569; }
  .pill.crediting { background:#dcfce7; color:#166534; }
  .pill.suspended { background:#fef3c7; color:#92400e; }
  .pill.closed    { background:#fee2e2; color:#991b1b; }
  @media (max-width: 900px) {
    .filters, .metrics, .grid-2 { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<header>
  <h1>🌱 Carbon Market Dashboard – ACCU scheme</h1>
  <div class="sub">Project developers, projects and Australian Carbon Credit Unit (ACCU) issuances</div>
</header>

<main>
  <div class="banner">
    <strong>Data source:</strong> <span id="ds-source">__SOURCE__</span> ·
    <span class="small">generated __GENERATED__</span>
  </div>

  <div class="filters">
    <div>
      <label for="f-method">Method</label>
      <select id="f-method" multiple></select>
    </div>
    <div>
      <label for="f-state">State / territory</label>
      <select id="f-state" multiple></select>
    </div>
    <div>
      <label for="f-dev">Developer (proponent)</label>
      <select id="f-dev" multiple></select>
    </div>
    <div>
      <label>Issuance year range <span class="small" id="f-year-label"></span></label>
      <div style="display:flex; gap:8px;">
        <select id="f-year-min"></select>
        <select id="f-year-max"></select>
      </div>
      <div style="margin-top:8px;">
        <button class="btn" id="btn-clear">Clear filters</button>
      </div>
    </div>
  </div>

  <div class="tabs" role="tablist">
    <button class="tab active" data-panel="overview">Overview</button>
    <button class="tab" data-panel="developers">Developers</button>
    <button class="tab" data-panel="projects">Projects</button>
    <button class="tab" data-panel="issuances">Issuances</button>
  </div>

  <section class="tab-panel active" id="overview">
    <div class="metrics" id="metrics"></div>
    <div class="card"><div class="card-title">Monthly ACCU issuances</div>
      <div id="chart-trend" style="height:320px;"></div></div>
    <div class="grid-2" style="margin-top:14px;">
      <div class="card"><div class="card-title">ACCUs by method</div>
        <div id="chart-method" style="height:340px;"></div></div>
      <div class="card"><div class="card-title">ACCUs by state</div>
        <div id="chart-state" style="height:320px;"></div></div>
    </div>
    <div class="grid-2" style="margin-top:14px;">
      <div class="card"><div class="card-title">Project status mix</div>
        <div id="chart-status" style="height:320px;"></div></div>
      <div class="card"><div class="card-title">Top developers</div>
        <div id="chart-top-dev" style="height:380px;"></div></div>
    </div>
  </section>

  <section class="tab-panel" id="developers">
    <div class="card" style="margin-bottom:14px;">
      <div class="card-title">Developer league table</div>
      <div class="table-wrap" style="margin:8px;"><table id="tbl-developers"></table></div>
    </div>
    <div class="card">
      <div class="card-title">Developer profile</div>
      <div style="padding:8px;">
        <select id="dev-select" style="padding:6px; border:1px solid var(--border); border-radius:6px;"></select>
      </div>
      <div class="metrics" id="dev-metrics" style="grid-template-columns:repeat(4,1fr); padding:0 8px;"></div>
      <div id="chart-dev-trend" style="height:280px; padding:0 8px;"></div>
      <div class="table-wrap" style="margin:8px;"><table id="tbl-dev-projects"></table></div>
    </div>
  </section>

  <section class="tab-panel" id="projects">
    <div class="row-actions">
      <input type="text" id="project-search" placeholder="Search project, ID, or developer…">
      <button class="btn" id="btn-export-projects">Download CSV</button>
    </div>
    <div class="small" id="project-count" style="margin-bottom:6px;"></div>
    <div class="table-wrap"><table id="tbl-projects"></table></div>
  </section>

  <section class="tab-panel" id="issuances">
    <div class="row-actions">
      <label class="small">Aggregate by:</label>
      <select id="issuance-grain">
        <option value="month">Month</option>
        <option value="quarter">Quarter</option>
        <option value="year">Year</option>
      </select>
      <span style="flex:1"></span>
      <button class="btn" id="btn-export-issuances">Download CSV</button>
    </div>
    <div class="card"><div class="card-title">ACCU issuances by method</div>
      <div id="chart-issue-stack" style="height:380px;"></div></div>
    <div class="small" style="margin:10px 0 6px;">Most recent 500 line items in view:</div>
    <div class="table-wrap"><table id="tbl-issuances"></table></div>
  </section>
</main>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
const $ = id => document.getElementById(id);

const fmtAccu = n => {
  n = +n || 0;
  if (n >= 1e6) return (n/1e6).toFixed(2) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(1) + 'k';
  return n.toLocaleString();
};
const fmtInt = n => (+n||0).toLocaleString();

const uniqSorted = (arr, key) =>
  [...new Set(arr.map(x => x[key]).filter(Boolean))].sort();

function fillMulti(el, opts) {
  el.innerHTML = opts.map(v => `<option value="${v}">${v}</option>`).join('');
}
function fillYears(el, years) {
  el.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');
}

// Filter state
const state = { method: [], stateF: [], dev: [], yearMin: null, yearMax: null,
                projectSearch: '', issuanceGrain: 'month', devSelected: null };

function init() {
  fillMulti($('f-method'), uniqSorted(DATA.projects, 'method'));
  fillMulti($('f-state'), uniqSorted(DATA.projects, 'state'));
  fillMulti($('f-dev'), uniqSorted(DATA.projects, 'developer'));

  const years = [...new Set(DATA.issuances
    .map(i => i.issuance_month && i.issuance_month.slice(0,4))
    .filter(Boolean))].sort();
  fillYears($('f-year-min'), years);
  fillYears($('f-year-max'), years);
  if (years.length) {
    $('f-year-min').value = years[0];
    $('f-year-max').value = years[years.length-1];
    state.yearMin = years[0]; state.yearMax = years[years.length-1];
  }

  ['f-method','f-state','f-dev'].forEach(id =>
    $(id).addEventListener('change', e => {
      const key = id === 'f-method' ? 'method' : id === 'f-state' ? 'stateF' : 'dev';
      state[key] = [...e.target.selectedOptions].map(o => o.value);
      render();
    })
  );
  $('f-year-min').addEventListener('change', e => { state.yearMin = e.target.value; render(); });
  $('f-year-max').addEventListener('change', e => { state.yearMax = e.target.value; render(); });

  $('btn-clear').addEventListener('click', () => {
    state.method = []; state.stateF = []; state.dev = [];
    state.yearMin = years[0]; state.yearMax = years[years.length-1];
    state.projectSearch = '';
    [...document.querySelectorAll('#f-method option,#f-state option,#f-dev option')]
      .forEach(o => o.selected = false);
    $('f-year-min').value = state.yearMin;
    $('f-year-max').value = state.yearMax;
    $('project-search').value = '';
    render();
  });

  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      $(t.dataset.panel).classList.add('active');
      // Plotly charts need a relayout when their tab becomes visible
      window.dispatchEvent(new Event('resize'));
    });
  });

  $('project-search').addEventListener('input', e => {
    state.projectSearch = e.target.value.toLowerCase();
    renderProjects();
  });
  $('btn-export-projects').addEventListener('click', () =>
    downloadCsv('accu_projects.csv', filteredProjects()));
  $('btn-export-issuances').addEventListener('click', () =>
    downloadCsv('accu_issuances.csv', filteredIssuances()));
  $('issuance-grain').addEventListener('change', e => {
    state.issuanceGrain = e.target.value;
    renderIssuancesTab();
  });
  $('dev-select').addEventListener('change', e => {
    state.devSelected = e.target.value;
    renderDeveloperProfile();
  });

  render();
}

function filteredProjects() {
  return DATA.projects.filter(p =>
    (!state.method.length || state.method.includes(p.method)) &&
    (!state.stateF.length || state.stateF.includes(p.state)) &&
    (!state.dev.length || state.dev.includes(p.developer))
  );
}

function filteredIssuances() {
  const projIds = new Set(filteredProjects().map(p => p.project_id));
  return DATA.issuances.filter(i => {
    if (!projIds.has(i.project_id)) return false;
    const yr = i.issuance_month && i.issuance_month.slice(0,4);
    if (state.yearMin && yr < state.yearMin) return false;
    if (state.yearMax && yr > state.yearMax) return false;
    return true;
  });
}

function projectsWithWindowTotals(projects, issuances) {
  const totals = {};
  for (const i of issuances) totals[i.project_id] = (totals[i.project_id]||0) + i.accus_issued;
  return projects.map(p => ({ ...p, accus_in_window: totals[p.project_id] || 0 }));
}

function render() {
  const projects = filteredProjects();
  const issuances = filteredIssuances();
  const projAug = projectsWithWindowTotals(projects, issuances);
  renderMetrics(projAug, issuances);
  renderTrend(issuances);
  renderByMethod(issuances);
  renderByState(issuances);
  renderStatusMix(projects);
  renderTopDev(projAug);
  renderDevelopersTab(projAug, issuances);
  renderProjects(projAug);
  renderIssuancesTab(issuances);
}

function renderMetrics(projects, issuances) {
  const totalIssued = issuances.reduce((s,i) => s + i.accus_issued, 0);
  const active = projects.filter(p => p.status === 'Crediting').length;
  const devs = new Set(projects.map(p => p.developer)).size;
  const avg = projects.length ? totalIssued / projects.length : 0;
  const latest = issuances.length
    ? issuances.map(i => i.issuance_month).sort().slice(-1)[0] : '–';
  $('metrics').innerHTML = [
    ['ACCUs issued', fmtAccu(totalIssued)],
    ['Projects in view', fmtInt(projects.length)],
    ['Active (crediting)', fmtInt(active)],
    ['Distinct developers', fmtInt(devs)],
    ['Latest issuance', latest],
  ].map(([k,v]) => `<div class="metric"><div class="label">${k}</div><div class="value">${v}</div></div>`).join('');
}

const PLOTLY_LAYOUT = { margin:{l:50,r:10,t:10,b:40}, paper_bgcolor:'#fff', plot_bgcolor:'#fff',
                        font:{family:'-apple-system,BlinkMacSystemFont,Segoe UI'} };

function renderTrend(issuances) {
  const buckets = {};
  for (const i of issuances) {
    if (!i.issuance_month) continue;
    buckets[i.issuance_month] = (buckets[i.issuance_month]||0) + i.accus_issued;
  }
  const months = Object.keys(buckets).sort();
  Plotly.newPlot('chart-trend',
    [{ x: months.map(m => m + '-01'), y: months.map(m => buckets[m]),
       type:'scatter', mode:'lines', fill:'tozeroy', line:{color:'#16a34a'} }],
    {...PLOTLY_LAYOUT, yaxis:{title:'ACCUs'}, xaxis:{type:'date'}}, {displayModeBar:false});
}

function renderByMethod(issuances) {
  const map = {};
  for (const i of issuances) map[i.method] = (map[i.method]||0) + i.accus_issued;
  const items = Object.entries(map).sort((a,b) => a[1]-b[1]);
  Plotly.newPlot('chart-method',
    [{ x: items.map(x=>x[1]), y: items.map(x=>x[0]), type:'bar', orientation:'h',
       marker:{color:'#16a34a'} }],
    {...PLOTLY_LAYOUT, margin:{l:200,r:10,t:10,b:40}}, {displayModeBar:false});
}

function renderByState(issuances) {
  const map = {};
  for (const i of issuances) map[i.state] = (map[i.state]||0) + i.accus_issued;
  const items = Object.entries(map).sort((a,b) => b[1]-a[1]);
  Plotly.newPlot('chart-state',
    [{ x: items.map(x=>x[0]), y: items.map(x=>x[1]), type:'bar', marker:{color:'#0ea5e9'} }],
    PLOTLY_LAYOUT, {displayModeBar:false});
}

function renderStatusMix(projects) {
  const map = {};
  for (const p of projects) map[p.status] = (map[p.status]||0) + 1;
  Plotly.newPlot('chart-status',
    [{ labels: Object.keys(map), values: Object.values(map), type:'pie', hole:0.5 }],
    {...PLOTLY_LAYOUT, margin:{l:10,r:10,t:10,b:10}}, {displayModeBar:false});
}

function renderTopDev(projects) {
  const map = {};
  for (const p of projects) map[p.developer] = (map[p.developer]||0) + p.accus_in_window;
  const items = Object.entries(map).sort((a,b) => a[1]-b[1]).slice(-10);
  Plotly.newPlot('chart-top-dev',
    [{ x: items.map(x=>x[1]), y: items.map(x=>x[0]), type:'bar', orientation:'h',
       marker:{color:'#ea580c'} }],
    {...PLOTLY_LAYOUT, margin:{l:220,r:10,t:10,b:40}}, {displayModeBar:false});
}

function renderDevelopersTab(projects, issuances) {
  const summary = {};
  for (const p of projects) {
    const s = summary[p.developer] = summary[p.developer] || {
      developer: p.developer, projects: 0, active: 0,
      states: new Set(), methods: new Set(), accus: 0,
    };
    s.projects++;
    if (p.status === 'Crediting') s.active++;
    s.states.add(p.state);
    s.methods.add(p.method);
    s.accus += p.accus_in_window;
  }
  const rows = Object.values(summary).sort((a,b) => b.accus - a.accus);
  const cols = [
    {k:'developer', t:'Developer'},
    {k:'projects', t:'Projects', n:true},
    {k:'active', t:'Active', n:true},
    {k:'states', t:'States', f: v => [...v].sort().join(', ')},
    {k:'methods', t:'Methods', f: v => [...v].sort().join(', ')},
    {k:'accus', t:'ACCUs (window)', n:true, f: fmtInt},
  ];
  $('tbl-developers').innerHTML = renderTable(cols, rows);

  // Developer profile selector
  const sel = $('dev-select');
  const prev = state.devSelected;
  sel.innerHTML = rows.map(r => `<option value="${r.developer}">${r.developer}</option>`).join('');
  if (prev && rows.some(r => r.developer === prev)) sel.value = prev;
  state.devSelected = sel.value;
  renderDeveloperProfile(projects, issuances);
}

function renderDeveloperProfile(projects, issuances) {
  if (!projects) projects = projectsWithWindowTotals(filteredProjects(), filteredIssuances());
  if (!issuances) issuances = filteredIssuances();
  const dev = state.devSelected;
  if (!dev) return;
  const dp = projects.filter(p => p.developer === dev);
  const di = issuances.filter(i => i.developer === dev);
  const totalIssued = di.reduce((s,i) => s + i.accus_issued, 0);
  $('dev-metrics').innerHTML = [
    ['Projects', fmtInt(dp.length)],
    ['Active', fmtInt(dp.filter(p => p.status==='Crediting').length)],
    ['ACCUs (window)', fmtAccu(totalIssued)],
    ['Methods used', fmtInt(new Set(dp.map(p => p.method)).size)],
  ].map(([k,v]) => `<div class="metric"><div class="label">${k}</div><div class="value">${v}</div></div>`).join('');

  const buckets = {};
  for (const i of di) buckets[i.issuance_month] = (buckets[i.issuance_month]||0) + i.accus_issued;
  const months = Object.keys(buckets).sort();
  Plotly.newPlot('chart-dev-trend',
    [{ x: months.map(m => m + '-01'), y: months.map(m => buckets[m]), type:'bar',
       marker:{color:'#16a34a'} }],
    {...PLOTLY_LAYOUT, height:260, xaxis:{type:'date'}}, {displayModeBar:false});

  const cols = [
    {k:'project_id', t:'Project ID'},
    {k:'project_name', t:'Project'},
    {k:'method', t:'Method'},
    {k:'state', t:'State'},
    {k:'status', t:'Status', f: s => `<span class="pill ${s.toLowerCase()}">${s}</span>`},
    {k:'crediting_start', t:'Crediting from'},
    {k:'accus_in_window', t:'ACCUs (window)', n:true, f: fmtInt},
  ];
  $('tbl-dev-projects').innerHTML = renderTable(cols, dp);
}

function renderProjects(projects) {
  if (!projects) projects = projectsWithWindowTotals(filteredProjects(), filteredIssuances());
  let rows = projects;
  if (state.projectSearch) {
    const q = state.projectSearch;
    rows = rows.filter(p =>
      (p.project_name||'').toLowerCase().includes(q) ||
      (p.project_id||'').toLowerCase().includes(q) ||
      (p.developer||'').toLowerCase().includes(q));
  }
  rows = [...rows].sort((a,b) => b.accus_in_window - a.accus_in_window);
  $('project-count').textContent = `${rows.length} project(s) in view`;
  const cols = [
    {k:'project_id', t:'ID'},
    {k:'project_name', t:'Project'},
    {k:'developer', t:'Developer'},
    {k:'method', t:'Method'},
    {k:'method_category', t:'Category'},
    {k:'state', t:'State'},
    {k:'status', t:'Status', f: s => `<span class="pill ${s.toLowerCase()}">${s}</span>`},
    {k:'registered', t:'Registered'},
    {k:'crediting_start', t:'Crediting from'},
    {k:'crediting_years', t:'Yrs', n:true},
    {k:'accus_in_window', t:'ACCUs (window)', n:true, f: fmtInt},
    {k:'total_accus_issued', t:'ACCUs (lifetime)', n:true, f: fmtInt},
  ];
  $('tbl-projects').innerHTML = renderTable(cols, rows);
}

function renderIssuancesTab(issuances) {
  if (!issuances) issuances = filteredIssuances();
  const grain = state.issuanceGrain;
  const bucketKey = m => {
    if (!m) return '';
    if (grain === 'year') return m.slice(0,4);
    if (grain === 'quarter') {
      const [y, mm] = m.split('-');
      const q = Math.floor((+mm-1)/3) + 1;
      return `${y}-Q${q}`;
    }
    return m;
  };
  const buckets = {}, methods = new Set();
  for (const i of issuances) {
    methods.add(i.method);
    const b = bucketKey(i.issuance_month);
    buckets[b] = buckets[b] || {};
    buckets[b][i.method] = (buckets[b][i.method] || 0) + i.accus_issued;
  }
  const labels = Object.keys(buckets).sort();
  const traces = [...methods].sort().map(m => ({
    name: m, type:'bar',
    x: labels, y: labels.map(l => buckets[l][m] || 0),
  }));
  Plotly.newPlot('chart-issue-stack', traces,
    {...PLOTLY_LAYOUT, barmode:'stack', legend:{orientation:'h', y:-0.25}}, {displayModeBar:false});

  const recent = [...issuances].sort((a,b) =>
    (b.issuance_month||'').localeCompare(a.issuance_month||'')).slice(0,500);
  const cols = [
    {k:'project_id', t:'Project ID'},
    {k:'project_name', t:'Project'},
    {k:'developer', t:'Developer'},
    {k:'method', t:'Method'},
    {k:'state', t:'State'},
    {k:'issuance_month', t:'Month'},
    {k:'accus_issued', t:'ACCUs', n:true, f: fmtInt},
  ];
  $('tbl-issuances').innerHTML = renderTable(cols, recent);
}

function renderTable(cols, rows) {
  const head = `<thead><tr>${cols.map(c =>
    `<th class="${c.n?'num':''}">${c.t}</th>`).join('')}</tr></thead>`;
  const body = `<tbody>${rows.map(r => `<tr>${cols.map(c => {
    const v = r[c.k];
    const cell = c.f ? c.f(v) : (v == null ? '' : v);
    return `<td class="${c.n?'num':''}">${cell}</td>`;
  }).join('')}</tr>`).join('')}</tbody>`;
  return head + body;
}

function downloadCsv(name, rows) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const esc = v => {
    if (v == null) return '';
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g,'""')}"` : s;
  };
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => esc(r[c])).join(','))].join('\n');
  const blob = new Blob([csv], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}

init();
</script>
</body>
</html>
"""


def build(output: Path) -> None:
    payload = _build_payload()
    payload_json = json.dumps(payload, default=_to_jsonable, separators=(",", ":"))
    # Guard against the unlikely case the payload contains a literal `</script>`.
    payload_json = payload_json.replace("</", "<\\/")

    html = (
        HTML_TEMPLATE
        .replace("__SOURCE__", payload["source"])
        .replace("__GENERATED__", payload["generated"])
        .replace("__PAYLOAD__", payload_json)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    size_kb = output.stat().st_size / 1024
    n_p = len(payload["projects"])
    n_i = len(payload["issuances"])
    print(f"[build_static_html] wrote {output} ({size_kb:.1f} KB, "
          f"{n_p} projects / {n_i} issuance rows, source: {payload['source']})")


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--output", type=Path,
                    default=ROOT / "dist" / "carbon_market_dashboard.html",
                    help="output HTML path (default: dist/carbon_market_dashboard.html)")
    args = ap.parse_args(argv)
    build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
