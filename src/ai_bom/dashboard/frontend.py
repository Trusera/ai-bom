"""Embedded HTML dashboard for AI-BOM."""

from __future__ import annotations


def get_dashboard_html() -> str:
    """Return a self-contained HTML single-page dashboard.

    The page is a dark-themed SPA using vanilla JS that calls /api/ endpoints.
    """
    return _DASHBOARD_HTML


_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI-BOM Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0d1117;
    --bg-card: #161b22;
    --bg-hover: #1c2333;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --orange: #d29922;
    --purple: #bc8cff;
  }
  [data-theme="light"] {
    --bg: #ffffff;
    --bg-card: #f6f8fa;
    --bg-hover: #eaeef2;
    --border: #d0d7de;
    --text: #1f2328;
    --text-dim: #656d76;
    --accent: #0969da;
    --green: #1a7f37;
    --red: #cf222e;
    --orange: #9a6700;
    --purple: #8250df;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }

  /* Layout */
  .header {
    background: var(--bg-card);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .header h1 { font-size: 20px; font-weight: 600; }
  .header h1 span { color: var(--accent); }
  .header .version { color: var(--text-dim); font-size: 13px; }
  .container { max-width: 1280px; margin: 0 auto; padding: 24px; }

  /* Cards */
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
  }
  .card h2 { font-size: 16px; margin-bottom: 12px; color: var(--text-dim); font-weight: 500; }

  /* Stats row */
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .stat-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }
  .stat-card .value { font-size: 32px; font-weight: 700; }
  .stat-card .label { color: var(--text-dim); font-size: 13px; margin-top: 4px; }

  /* Table */
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }
  th { color: var(--text-dim); font-weight: 500; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }
  tr:hover { background: var(--bg-hover); }
  tr { cursor: pointer; }
  thead tr { cursor: default; }
  thead tr:hover { background: transparent; }

  /* Badges */
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge-critical { background: #f8514922; color: var(--red); border: 1px solid #f8514944; }
  .badge-high { background: #d2992222; color: var(--orange); border: 1px solid #d2992244; }
  .badge-medium { background: #58a6ff22; color: var(--accent); border: 1px solid #58a6ff44; }
  .badge-low { background: #3fb95022; color: var(--green); border: 1px solid #3fb95044; }

  /* Buttons */
  .btn {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-card);
    color: var(--text);
    cursor: pointer;
    font-size: 13px;
    transition: background 0.15s;
  }
  .btn:hover { background: var(--bg-hover); }
  .btn-danger { border-color: var(--red); color: var(--red); }
  .btn-danger:hover { background: #f8514922; }
  .btn-primary { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }
  .btn-primary:hover { opacity: 0.9; }

  /* Compare */
  .compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .diff-added { color: var(--green); }
  .diff-removed { color: var(--red); }
  .diff-common { color: var(--text-dim); }

  /* Charts */
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
  .chart-wrap { max-height: 300px; display: flex; justify-content: center; }

  /* Responsive */
  @media (max-width: 768px) {
    .charts { grid-template-columns: 1fr; }
    .compare-grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }

  /* Navigation breadcrumb */
  .breadcrumb { margin-bottom: 16px; font-size: 14px; }
  .breadcrumb a { color: var(--accent); }

  /* Filter bar */
  .filter-bar { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
  .filter-bar input, .filter-bar select {
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text);
    font-size: 13px;
  }

  /* Compare selection */
  .compare-bar {
    background: var(--bg-card);
    border: 1px solid var(--accent);
    border-radius: 8px;
    padding: 10px 16px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .compare-bar .selected { color: var(--accent); }

  .hidden { display: none !important; }

  /* Loading */
  .loading { text-align: center; padding: 40px; color: var(--text-dim); }

  /* Theme toggle */
  .theme-toggle {
    background: none; border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); cursor: pointer; font-size: 18px; padding: 4px 10px;
    transition: background 0.15s;
  }
  .theme-toggle:hover { background: var(--bg-hover); }

  /* Modal */
  .modal-overlay {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.6); z-index: 1000; display: flex;
    align-items: center; justify-content: center;
  }
  .modal {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; max-width: 600px; width: 90%;
    max-height: 80vh; overflow-y: auto; position: relative;
  }
  .modal h3 { font-size: 18px; margin-bottom: 16px; }
  .modal-close {
    position: absolute; top: 12px; right: 16px; background: none;
    border: none; color: var(--text-dim); font-size: 22px; cursor: pointer;
  }
  .modal-close:hover { color: var(--text); }
  .modal-row { display: flex; padding: 8px 0; border-bottom: 1px solid var(--border); }
  .modal-label { width: 140px; color: var(--text-dim); font-size: 13px; flex-shrink: 0; }
  .modal-value { flex: 1; font-size: 14px; word-break: break-all; }

  /* Export bar */
  .export-bar { display: flex; gap: 8px; }
</style>
</head>
<body>

<div class="header">
  <h1><span>AI-BOM</span> Dashboard</h1>
  <div style="display:flex;align-items:center;gap:12px">
    <div class="version" id="app-version"></div>
    <button class="theme-toggle" id="theme-toggle" title="Toggle theme">&#9790;</button>
  </div>
</div>
<div id="modal-container"></div>

<div class="container">
  <!-- Scan list view -->
  <div id="view-list">
    <div class="stats" id="global-stats"></div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h2>Scan History</h2>
        <label style="font-size:13px;color:var(--text-dim)">
          <input type="checkbox" id="compare-mode"> Compare mode
        </label>
      </div>
      <div id="compare-bar" class="compare-bar hidden">
        <span>Select two scans to compare. Selected: <span class="selected" id="compare-count">0</span>/2</span>
        <button class="btn btn-primary" id="compare-go" disabled>Compare</button>
      </div>
      <div id="scan-list"><div class="loading">Loading scans...</div></div>
    </div>
  </div>

  <!-- Scan detail view -->
  <div id="view-detail" class="hidden">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <div class="breadcrumb" style="margin-bottom:0"><a href="#" onclick="showList();return false">Scans</a> / <span id="detail-title"></span></div>
      <div class="export-bar">
        <button class="btn" onclick="exportCSV()">Export CSV</button>
        <button class="btn" onclick="exportJSON()">Export JSON</button>
      </div>
    </div>
    <div class="stats" id="detail-stats" style="margin-top:16px"></div>
    <div class="charts">
      <div class="card"><h2>Severity Distribution</h2><div class="chart-wrap"><canvas id="chart-severity"></canvas></div></div>
      <div class="card"><h2>Component Types</h2><div class="chart-wrap"><canvas id="chart-types"></canvas></div></div>
    </div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h2>Components</h2>
        <div class="filter-bar">
          <input type="text" id="filter-search" placeholder="Search components...">
          <select id="filter-severity"><option value="">All Severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
          <select id="filter-type"><option value="">All Types</option></select>
        </div>
      </div>
      <div id="component-table"></div>
    </div>
    <div style="margin-top:12px">
      <button class="btn btn-danger" onclick="deleteScan()">Delete this scan</button>
    </div>
  </div>

  <!-- Compare view -->
  <div id="view-compare" class="hidden">
    <div class="breadcrumb"><a href="#" onclick="showList();return false">Scans</a> / Compare</div>
    <div id="compare-content"></div>
  </div>
</div>

<script>
const API = '/api';
let allScans = [];
let currentScan = null;
let compareSelection = [];
let chartSeverity = null;
let chartTypes = null;

// HTML escaping to prevent XSS
function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(String(s)));
  return d.innerHTML;
}

// Helpers
function severityBadge(sev) {
  return '<span class="badge badge-' + esc(sev) + '">' + esc(sev).toUpperCase() + '</span>';
}

function shortPath(p) {
  if (!p) return '';
  const parts = p.split('/');
  return parts.length > 3 ? '.../' + parts.slice(-2).join('/') : p;
}

function formatDate(ts) {
  try { return new Date(ts).toLocaleString(); } catch(e) { return ts; }
}

function highestSeverity(summary) {
  if (!summary || !summary.by_severity) return 'low';
  for (const s of ['critical','high','medium','low']) {
    if (summary.by_severity[s] > 0) return s;
  }
  return 'low';
}

// API calls
async function fetchScans() {
  try {
    const r = await fetch(API + '/scans');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch(e) {
    document.getElementById('scan-list').innerHTML =
      '<p style="color:var(--red);padding:20px">Failed to load scans: ' + esc(e.message) + '</p>';
    return [];
  }
}

async function fetchScan(id) {
  try {
    const r = await fetch(API + '/scans/' + encodeURIComponent(id));
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch(e) {
    document.getElementById('component-table').innerHTML =
      '<p style="color:var(--red);padding:20px">Failed to load scan: ' + esc(e.message) + '</p>';
    return {components:[], summary:{}};
  }
}

async function apiDeleteScan(id) {
  await fetch(API + '/scans/' + encodeURIComponent(id), {method:'DELETE'});
}

async function fetchCompare(id1, id2) {
  try {
    const r = await fetch(API + '/compare?scan_id_1=' + encodeURIComponent(id1) + '&scan_id_2=' + encodeURIComponent(id2));
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch(e) {
    document.getElementById('compare-content').innerHTML =
      '<p style="color:var(--red);padding:20px">Failed to compare scans: ' + esc(e.message) + '</p>';
    return {scan_a:{components:[],summary:{}},scan_b:{components:[],summary:{}},added:[],removed:[],common:[]};
  }
}

// Views
function showList() {
  document.getElementById('view-list').classList.remove('hidden');
  document.getElementById('view-detail').classList.add('hidden');
  document.getElementById('view-compare').classList.add('hidden');
  loadScans();
}

async function loadScans() {
  allScans = await fetchScans();
  renderGlobalStats();
  renderScanList();
}

function renderGlobalStats() {
  const el = document.getElementById('global-stats');
  const totalScans = allScans.length;
  let totalComponents = 0;
  let highestRisk = 0;
  let targets = new Set();
  allScans.forEach(s => {
    totalComponents += (s.summary && s.summary.total_components) || 0;
    const r = (s.summary && s.summary.highest_risk_score) || 0;
    if (r > highestRisk) highestRisk = r;
    targets.add(s.target_path);
  });
  el.innerHTML = [
    statCard(totalScans, 'Total Scans', 'var(--accent)'),
    statCard(totalComponents, 'Components Found', 'var(--purple)'),
    statCard(targets.size, 'Unique Targets', 'var(--green)'),
    statCard(highestRisk, 'Highest Risk Score', highestRisk >= 70 ? 'var(--red)' : highestRisk >= 40 ? 'var(--orange)' : 'var(--green)'),
  ].join('');
}

function statCard(value, label, color) {
  return '<div class="stat-card"><div class="value" style="color:' + color + '">' + esc(value) + '</div><div class="label">' + esc(label) + '</div></div>';
}

function renderScanList() {
  const el = document.getElementById('scan-list');
  if (allScans.length === 0) {
    el.innerHTML = '<p style="color:var(--text-dim);padding:20px">No scans yet. Run <code>ai-bom scan --save-dashboard</code> to save scan results.</p>';
    return;
  }
  const isCompare = document.getElementById('compare-mode').checked;
  let html = '<table><thead><tr>';
  if (isCompare) html += '<th></th>';
  html += '<th>Date</th><th>Target</th><th>Components</th><th>Highest Severity</th><th>Risk Score</th><th>Duration</th></tr></thead><tbody>';
  allScans.forEach(s => {
    const sev = highestSeverity(s.summary);
    const checked = compareSelection.includes(s.id) ? 'checked' : '';
    const escapedId = esc(s.id);
    html += '<tr onclick="' + (isCompare ? '' : "showDetail('" + escapedId + "')") + '">';
    if (isCompare) html += '<td><input type="checkbox" class="cmp-check" data-id="' + escapedId + '" ' + checked + ' onclick="event.stopPropagation();toggleCompare(this)"></td>';
    html += '<td>' + esc(formatDate(s.timestamp)) + '</td>';
    html += '<td title="' + esc(s.target_path) + '">' + esc(shortPath(s.target_path)) + '</td>';
    html += '<td>' + esc((s.summary && s.summary.total_components) || 0) + '</td>';
    html += '<td>' + severityBadge(sev) + '</td>';
    html += '<td>' + esc((s.summary && s.summary.highest_risk_score) || 0) + '</td>';
    html += '<td>' + esc((s.scan_duration != null) ? s.scan_duration.toFixed(2) + 's' : '-') + '</td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

// Compare mode
document.getElementById('compare-mode').addEventListener('change', function() {
  const bar = document.getElementById('compare-bar');
  if (this.checked) {
    bar.classList.remove('hidden');
    compareSelection = [];
    updateCompareUI();
  } else {
    bar.classList.add('hidden');
    compareSelection = [];
  }
  renderScanList();
});

function toggleCompare(checkbox) {
  const id = checkbox.dataset.id;
  if (checkbox.checked) {
    if (compareSelection.length < 2) compareSelection.push(id);
    else { checkbox.checked = false; return; }
  } else {
    compareSelection = compareSelection.filter(x => x !== id);
  }
  updateCompareUI();
}

function updateCompareUI() {
  document.getElementById('compare-count').textContent = compareSelection.length;
  document.getElementById('compare-go').disabled = compareSelection.length !== 2;
}

document.getElementById('compare-go').addEventListener('click', async function() {
  if (compareSelection.length !== 2) return;
  const data = await fetchCompare(compareSelection[0], compareSelection[1]);
  showCompareView(data);
});

function showCompareView(data) {
  document.getElementById('view-list').classList.add('hidden');
  document.getElementById('view-detail').classList.add('hidden');
  document.getElementById('view-compare').classList.remove('hidden');

  const el = document.getElementById('compare-content');
  let html = '<div class="compare-grid">';
  [data.scan_a, data.scan_b].forEach(scan => {
    html += '<div class="card"><h2>' + esc(shortPath(scan.target_path)) + '</h2>';
    html += '<p style="color:var(--text-dim);font-size:13px">' + esc(formatDate(scan.timestamp)) + '</p>';
    html += '<p style="margin-top:8px">Components: <strong>' + esc(scan.components.length) + '</strong></p>';
    html += '<p>Risk Score: <strong>' + esc((scan.summary && scan.summary.highest_risk_score) || 0) + '</strong></p>';
    html += '</div>';
  });
  html += '</div>';

  html += '<div class="card"><h2>Differences</h2>';
  if (data.added.length) {
    html += '<h3 class="diff-added" style="margin:8px 0 4px">+ Added (' + data.added.length + ')</h3><ul>';
    data.added.forEach(n => html += '<li class="diff-added">' + esc(n) + '</li>');
    html += '</ul>';
  }
  if (data.removed.length) {
    html += '<h3 class="diff-removed" style="margin:8px 0 4px">- Removed (' + data.removed.length + ')</h3><ul>';
    data.removed.forEach(n => html += '<li class="diff-removed">' + esc(n) + '</li>');
    html += '</ul>';
  }
  if (data.common.length) {
    html += '<h3 class="diff-common" style="margin:8px 0 4px">Unchanged (' + data.common.length + ')</h3><ul>';
    data.common.forEach(n => html += '<li class="diff-common">' + esc(n) + '</li>');
    html += '</ul>';
  }
  if (!data.added.length && !data.removed.length) {
    html += '<p style="color:var(--text-dim)">No differences in component names.</p>';
  }
  html += '</div>';
  el.innerHTML = html;
}

// Detail view
async function showDetail(id) {
  currentScan = await fetchScan(id);
  document.getElementById('view-list').classList.add('hidden');
  document.getElementById('view-detail').classList.remove('hidden');
  document.getElementById('view-compare').classList.add('hidden');
  document.getElementById('detail-title').textContent = shortPath(currentScan.target_path) + ' (' + formatDate(currentScan.timestamp) + ')';
  renderDetailStats();
  renderCharts();
  populateTypeFilter();
  renderComponents();
}

function renderDetailStats() {
  const s = currentScan.summary || {};
  const el = document.getElementById('detail-stats');
  el.innerHTML = [
    statCard(s.total_components || 0, 'Components', 'var(--accent)'),
    statCard(s.total_files_scanned || 0, 'Files Scanned', 'var(--purple)'),
    statCard(s.highest_risk_score || 0, 'Highest Risk', (s.highest_risk_score||0) >= 70 ? 'var(--red)' : 'var(--green)'),
    statCard((s.scan_duration_seconds || 0).toFixed(2) + 's', 'Duration', 'var(--text-dim)'),
  ].join('');
}

function renderCharts() {
  const s = currentScan.summary || {};

  // Severity chart
  if (chartSeverity) chartSeverity.destroy();
  const sevData = s.by_severity || {};
  const sevCtx = document.getElementById('chart-severity').getContext('2d');
  chartSeverity = new Chart(sevCtx, {
    type: 'doughnut',
    data: {
      labels: ['Critical','High','Medium','Low'],
      datasets: [{
        data: [sevData.critical||0, sevData.high||0, sevData.medium||0, sevData.low||0],
        backgroundColor: ['#f85149','#d29922','#58a6ff','#3fb950'],
        borderColor: '#161b22',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { position: 'bottom', labels: { color: '#8b949e' } } }
    }
  });

  // Type chart
  if (chartTypes) chartTypes.destroy();
  const typeData = s.by_type || {};
  const typeLabels = Object.keys(typeData);
  const typeValues = Object.values(typeData);
  const typeCtx = document.getElementById('chart-types').getContext('2d');
  chartTypes = new Chart(typeCtx, {
    type: 'bar',
    data: {
      labels: typeLabels.map(l => l.replace(/_/g,' ')),
      datasets: [{
        label: 'Count',
        data: typeValues,
        backgroundColor: '#58a6ff',
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      scales: {
        x: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
        y: { ticks: { color: '#8b949e', stepSize: 1 }, grid: { color: '#30363d' }, beginAtZero: true }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function populateTypeFilter() {
  const sel = document.getElementById('filter-type');
  sel.innerHTML = '<option value="">All Types</option>';
  const types = new Set(currentScan.components.map(c => c.type));
  types.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t.replace(/_/g, ' ');
    sel.appendChild(opt);
  });
}

function renderComponents() {
  const search = (document.getElementById('filter-search').value || '').toLowerCase();
  const sevFilter = document.getElementById('filter-severity').value;
  const typeFilter = document.getElementById('filter-type').value;

  let comps = currentScan.components || [];
  if (search) comps = comps.filter(c => c.name.toLowerCase().includes(search) || (c.provider||'').toLowerCase().includes(search));
  if (sevFilter) comps = comps.filter(c => c.risk && c.risk.severity === sevFilter);
  if (typeFilter) comps = comps.filter(c => c.type === typeFilter);

  const el = document.getElementById('component-table');
  if (comps.length === 0) {
    el.innerHTML = '<p style="color:var(--text-dim);padding:10px">No components match the current filters.</p>';
    return;
  }
  let html = '<table><thead><tr><th>Name</th><th>Type</th><th>Provider</th><th>Version</th><th>Severity</th><th>Risk Score</th><th>File</th></tr></thead><tbody>';
  // Store filtered components for modal access
  window._filteredComponents = comps;
  comps.forEach((c, idx) => {
    const sev = (c.risk && c.risk.severity) || 'low';
    const score = (c.risk && c.risk.score) || 0;
    const filePath = (c.location && c.location.file_path) || '';
    html += '<tr onclick="showComponentModal(' + idx + ')">';
    html += '<td><strong>' + esc(c.name) + '</strong></td>';
    html += '<td>' + esc((c.type||'').replace(/_/g,' ')) + '</td>';
    html += '<td>' + esc(c.provider||'-') + '</td>';
    html += '<td>' + esc(c.version||'-') + '</td>';
    html += '<td>' + severityBadge(sev) + '</td>';
    html += '<td>' + esc(score) + '</td>';
    html += '<td title="' + esc(filePath) + '">' + esc(shortPath(filePath)) + '</td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

document.getElementById('filter-search').addEventListener('input', renderComponents);
document.getElementById('filter-severity').addEventListener('change', renderComponents);
document.getElementById('filter-type').addEventListener('change', renderComponents);

async function deleteScan() {
  if (!currentScan) return;
  if (!confirm('Delete this scan permanently?')) return;
  await apiDeleteScan(currentScan.id);
  showList();
}

// Theme toggle
function initTheme() {
  const saved = localStorage.getItem('ai-bom-theme');
  if (saved === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
    document.getElementById('theme-toggle').innerHTML = '&#9728;';
  }
}
document.getElementById('theme-toggle').addEventListener('click', function() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  if (isLight) {
    document.documentElement.removeAttribute('data-theme');
    this.innerHTML = '&#9790;';
    localStorage.setItem('ai-bom-theme', 'dark');
  } else {
    document.documentElement.setAttribute('data-theme', 'light');
    this.innerHTML = '&#9728;';
    localStorage.setItem('ai-bom-theme', 'light');
  }
});

// Export functions
function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function exportCSV() {
  if (!currentScan || !currentScan.components) return;
  const headers = ['Name','Type','Provider','Version','Severity','Risk Score','File Path','Flags','Source'];
  const rows = currentScan.components.map(c => [
    c.name || '',
    (c.type || '').replace(/_/g,' '),
    c.provider || '',
    c.version || '',
    (c.risk && c.risk.severity) || '',
    (c.risk && c.risk.score) || 0,
    (c.location && c.location.file_path) || '',
    (c.flags || []).join('; '),
    c.source || ''
  ]);
  const csv = [headers, ...rows].map(r => r.map(v => '"' + String(v).replace(/"/g,'""') + '"').join(',')).join('\\n');
  downloadBlob(csv, 'ai-bom-scan.csv', 'text/csv');
}

function exportJSON() {
  if (!currentScan) return;
  downloadBlob(JSON.stringify(currentScan, null, 2), 'ai-bom-scan.json', 'application/json');
}

// Component detail modal
function showComponentModal(idx) {
  const comps = window._filteredComponents || [];
  const c = comps[idx];
  if (!c) return;
  const sev = (c.risk && c.risk.severity) || 'low';
  const score = (c.risk && c.risk.score) || 0;
  const filePath = (c.location && c.location.file_path) || '';
  const line = (c.location && c.location.line_number) || '';
  const flags = (c.flags || []).join(', ') || 'None';
  const riskFactors = (c.risk && c.risk.factors) ? c.risk.factors.join(', ') : 'None';
  const metadata = c.metadata ? Object.entries(c.metadata).map(([k,v]) => esc(k) + ': ' + esc(v)).join('<br>') : 'None';

  const el = document.getElementById('modal-container');
  el.innerHTML = '<div class="modal-overlay" onclick="closeModal(event)">' +
    '<div class="modal" onclick="event.stopPropagation()">' +
    '<button class="modal-close" onclick="closeModal()">&times;</button>' +
    '<h3>' + esc(c.name) + '</h3>' +
    modalRow('Type', (c.type || '').replace(/_/g, ' ')) +
    modalRow('Provider', c.provider || '-') +
    modalRow('Version', c.version || '-') +
    modalRow('Severity', severityBadge(sev)) +
    modalRow('Risk Score', score) +
    modalRow('File Path', filePath || '-') +
    (line ? modalRow('Line', line) : '') +
    modalRow('Source', c.source || '-') +
    modalRow('Flags', flags) +
    modalRow('Risk Factors', riskFactors) +
    modalRow('Metadata', metadata) +
    '</div></div>';
}

function modalRow(label, value) {
  return '<div class="modal-row"><div class="modal-label">' + esc(label) + '</div><div class="modal-value">' + (typeof value === 'string' && value.includes('<') ? value : esc(value)) + '</div></div>';
}

function closeModal(event) {
  if (event && event.target && !event.target.classList.contains('modal-overlay')) return;
  document.getElementById('modal-container').innerHTML = '';
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') document.getElementById('modal-container').innerHTML = '';
});

// Init
initTheme();
showList();
</script>
</body>
</html>
"""
