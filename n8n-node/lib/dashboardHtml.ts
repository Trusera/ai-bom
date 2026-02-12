/**
 * Self-contained HTML dashboard generator for Trusera AI-BOM scan results.
 * Ported from Python src/ai_bom/dashboard/frontend.py, adapted for
 * static embedded data (no API calls) with optional AES-256-GCM encryption.
 */

import { randomBytes, pbkdf2Sync, createCipheriv } from 'crypto';
import type { ScanResult } from './models';
import { REMEDIATION_MAP } from './config';

/**
 * Generate a self-contained HTML dashboard for the given scan results.
 * If `password` is provided, the scan data is AES-256-GCM encrypted and
 * the page shows a password prompt that decrypts client-side.
 */
export function generateDashboardHtml(
  scanResult: ScanResult,
  password?: string,
): string {
  const jsonPayload = JSON.stringify(scanResult);

  let dataScript: string;
  let decryptionScript = '';
  let passwordFormHtml = '';

  const remediationScript = `<script>var REMEDIATION_MAP = ${JSON.stringify(REMEDIATION_MAP)};</script>`;

  if (password) {
    const salt = randomBytes(16);
    const iv = randomBytes(12);
    const key = pbkdf2Sync(password, salt, 100_000, 32, 'sha256');
    const cipher = createCipheriv('aes-256-gcm', key, iv);
    const encrypted = Buffer.concat([
      cipher.update(jsonPayload, 'utf8'),
      cipher.final(),
    ]);
    const authTag = cipher.getAuthTag();
    const blob = Buffer.concat([encrypted, authTag]);

    dataScript = `<script>
var ENCRYPTED_DATA = "${blob.toString('base64')}";
var SALT = "${salt.toString('base64')}";
var IV = "${iv.toString('base64')}";
var SCAN_DATA = null;
</script>`;

    decryptionScript = `
async function decryptData(pwd) {
  try {
    var enc = new TextEncoder();
    var saltBuf = Uint8Array.from(atob(SALT), function(c) { return c.charCodeAt(0); });
    var ivBuf = Uint8Array.from(atob(IV), function(c) { return c.charCodeAt(0); });
    var blobBuf = Uint8Array.from(atob(ENCRYPTED_DATA), function(c) { return c.charCodeAt(0); });
    var ciphertext = blobBuf.slice(0, blobBuf.length - 16);
    var tag = blobBuf.slice(blobBuf.length - 16);
    var combined = new Uint8Array(ciphertext.length + tag.length);
    combined.set(ciphertext);
    combined.set(tag, ciphertext.length);
    var keyMaterial = await crypto.subtle.importKey('raw', enc.encode(pwd), 'PBKDF2', false, ['deriveKey']);
    var aesKey = await crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt: saltBuf, iterations: 100000, hash: 'SHA-256' },
      keyMaterial, { name: 'AES-GCM', length: 256 }, false, ['decrypt']
    );
    var decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: ivBuf }, aesKey, combined);
    return JSON.parse(new TextDecoder().decode(decrypted));
  } catch (e) {
    return null;
  }
}

async function handleLogin(e) {
  e.preventDefault();
  var pwd = document.getElementById('pwd-input').value;
  var errEl = document.getElementById('pwd-error');
  errEl.classList.add('hidden');
  var data = await decryptData(pwd);
  if (!data) {
    errEl.classList.remove('hidden');
    return;
  }
  SCAN_DATA = data;
  try { sessionStorage.setItem('trusera-pwd', pwd); } catch(e) {}
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('dashboard').classList.remove('hidden');
  renderDashboard();
}

async function trySessionRestore() {
  var saved; try { saved = sessionStorage.getItem('trusera-pwd'); } catch(e) {}
  if (saved) {
    var data = await decryptData(saved);
    if (data) {
      SCAN_DATA = data;
      document.getElementById('login-screen').classList.add('hidden');
      document.getElementById('dashboard').classList.remove('hidden');
      renderDashboard();
      return;
    }
  }
  document.getElementById('login-screen').classList.remove('hidden');
}
`;

    passwordFormHtml = `
<div id="login-screen" class="login-screen hidden">
  <div class="login-box">
    <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" width="48" height="48" style="margin-bottom:16px">
      <path d="M32 4L56 18V46L32 60L8 46V18L32 4Z" fill="#0F172A" stroke="#3B82F6" stroke-width="2"/>
      <text x="32" y="40" text-anchor="middle" font-family="Arial,sans-serif" font-size="28" font-weight="bold" fill="#3B82F6">T</text>
    </svg>
    <h2>Trusera Dashboard</h2>
    <p style="color:var(--text-dim);font-size:13px;margin-bottom:16px">Enter password to view scan results</p>
    <form onsubmit="handleLogin(event)">
      <input type="password" id="pwd-input" placeholder="Password" autofocus
        style="width:100%;padding:10px 14px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;margin-bottom:10px">
      <button type="submit" class="btn btn-primary" style="width:100%;padding:10px">Unlock</button>
    </form>
    <p id="pwd-error" class="hidden" style="color:var(--red);font-size:13px;margin-top:10px">Incorrect password. Please try again.</p>
  </div>
</div>`;
  } else {
    dataScript = `<script>var SCAN_DATA = ${jsonPayload};</script>`;
  }

  const dashboardHiddenClass = password ? ' hidden' : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trusera AI-BOM Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"><\/script>
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
  .header-right { display:flex; align-items:center; gap:12px; }
  .header .version { color: var(--text-dim); font-size: 13px; }
  .container { max-width: 1280px; margin: 0 auto; padding: 24px; }
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
  }
  .card h2 { font-size: 16px; margin-bottom: 12px; color: var(--text-dim); font-weight: 500; }
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
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }
  th { color: var(--text-dim); font-weight: 500; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }
  tbody tr:hover { background: var(--bg-hover); }
  tbody tr { cursor: pointer; }
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
  .btn-primary { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }
  .btn-primary:hover { opacity: 0.9; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
  .charts-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px; }
  .wf-row { cursor: pointer; }
  .wf-row:hover { background: var(--bg-hover); }
  .filter-count { color: var(--text-dim); font-size: 13px; margin-top: 4px; }
  .chart-wrap { max-height: 300px; display: flex; justify-content: center; }
  .filter-bar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .filter-bar input, .filter-bar select {
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text);
    font-size: 13px;
  }
  .modal-overlay {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.6); z-index: 1000; display: flex;
    align-items: center; justify-content: center;
  }
  .modal {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px; max-width: 720px; width: 90%;
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
  .theme-toggle {
    background: none; border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); cursor: pointer; font-size: 18px; padding: 4px 10px;
    transition: background 0.15s;
  }
  .theme-toggle:hover { background: var(--bg-hover); }
  .login-screen {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: var(--bg); z-index: 2000; display: flex;
    align-items: center; justify-content: center;
  }
  .login-box {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 32px; max-width: 360px; width: 90%;
    text-align: center;
  }
  .login-box h2 { margin-bottom: 4px; }
  .export-bar { display: flex; gap: 8px; }
  .flag-card {
    border-left: 4px solid var(--border);
    background: var(--bg);
    border-radius: 0 8px 8px 0;
    padding: 14px 16px;
    margin-bottom: 10px;
  }
  .flag-card.severity-critical { border-left-color: var(--red); }
  .flag-card.severity-high { border-left-color: var(--orange); }
  .flag-card.severity-medium { border-left-color: var(--accent); }
  .flag-card.severity-low { border-left-color: var(--green); }
  .flag-card-header { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
  .flag-card-header code { font-size:13px; font-weight:600; }
  .flag-card p { font-size:13px; color:var(--text-dim); margin:4px 0; line-height:1.5; }
  .flag-card strong { color:var(--text); font-size:12px; text-transform:uppercase; letter-spacing:0.5px; }
  .owasp-tag {
    display:inline-block; padding:2px 8px; border-radius:4px;
    font-size:11px; font-weight:600; background:var(--purple); color:#fff;
    margin-top:6px;
  }
  .flag-section { margin-top:16px; }
  .flag-section h4 { font-size:14px; margin-bottom:10px; color:var(--text-dim); }
  .hidden { display: none !important; }
  @media (max-width: 768px) {
    .charts { grid-template-columns: 1fr; }
    .charts-3 { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
  @media (min-width: 769px) and (max-width: 1100px) {
    .charts-3 { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>

${dataScript}
${remediationScript}
${passwordFormHtml}

<div id="dashboard" class="${dashboardHiddenClass}">
<div class="header">
  <h1><span>Trusera</span> AI-BOM Dashboard</h1>
  <div class="header-right">
    <div class="version" id="app-version"></div>
    <button class="theme-toggle" id="theme-toggle" title="Toggle theme">&#9790;</button>
  </div>
</div>
<div id="modal-container"></div>

<div class="container">
  <div class="stats" id="stat-cards"></div>
  <div class="charts-3">
    <div class="card"><h2>Severity Distribution</h2><div class="chart-wrap"><canvas id="chart-severity"></canvas></div></div>
    <div class="card"><h2>Component Types</h2><div class="chart-wrap"><canvas id="chart-types"></canvas></div></div>
    <div class="card"><h2>OWASP LLM Top 10</h2><div class="chart-wrap"><canvas id="chart-owasp"></canvas></div></div>
  </div>
  <div class="card" id="workflows-section">
    <h2>Scanned Workflows</h2>
    <div id="workflows-table"></div>
  </div>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px">
      <div>
        <h2 style="margin-bottom:0">Findings</h2>
        <div class="filter-count" id="filter-count"></div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <div class="filter-bar">
          <input type="text" id="filter-search" placeholder="Search components...">
          <select id="filter-severity"><option value="">All Severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
          <select id="filter-type"><option value="">All Types</option></select>
          <select id="filter-workflow"><option value="">All Workflows</option></select>
        </div>
        <div class="export-bar">
          <button class="btn" onclick="exportCSV()">CSV</button>
          <button class="btn" onclick="exportJSON()">JSON</button>
        </div>
      </div>
    </div>
    <div id="component-table"></div>
  </div>
</div>
</div>

<script>
function esc(s) {
  if (s == null) return '';
  var d = document.createElement('div');
  d.appendChild(document.createTextNode(String(s)));
  return d.innerHTML;
}

function severityBadge(sev) {
  return '<span class="badge badge-' + esc(sev) + '">' + esc(sev).toUpperCase() + '</span>';
}

function statCard(value, label, color) {
  return '<div class="stat-card"><div class="value" style="color:' + color + '">' + esc(value) + '</div><div class="label">' + esc(label) + '</div></div>';
}

var chartSeverity = null;
var chartTypes = null;
var chartOwasp = null;
var filteredComponents = [];
var activeWorkflowFilter = '';

${decryptionScript}

function renderDashboard() {
  if (!SCAN_DATA) return;
  var data = SCAN_DATA;
  document.getElementById('app-version').textContent = 'v' + (data.aiBomVersion || '0.1.0');

  var s = data.summary || {};
  var hr = s.highestRiskScore || 0;
  document.getElementById('stat-cards').innerHTML = [
    statCard(s.totalComponents || 0, 'Components', 'var(--accent)'),
    statCard(s.totalFilesScanned || 0, 'Workflows Scanned', 'var(--purple)'),
    statCard(hr, 'Highest Risk Score', hr >= 70 ? 'var(--red)' : hr >= 40 ? 'var(--orange)' : 'var(--green)'),
    statCard((s.scanDurationSeconds || 0).toFixed(2) + 's', 'Scan Duration', 'var(--text-dim)'),
  ].join('');

  renderCharts(data);
  populateTypeFilter(data);
  populateWorkflowFilter(data);
  renderWorkflowsTable(data);
  renderComponents(data);

  document.getElementById('filter-search').addEventListener('input', function() { renderComponents(data); });
  document.getElementById('filter-severity').addEventListener('change', function() { renderComponents(data); });
  document.getElementById('filter-type').addEventListener('change', function() { renderComponents(data); });
  document.getElementById('filter-workflow').addEventListener('change', function() { renderComponents(data); });
}

function renderCharts(data) {
  var s = data.summary || {};
  if (chartSeverity) chartSeverity.destroy();
  var sev = s.bySeverity || {};
  chartSeverity = new Chart(document.getElementById('chart-severity').getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Critical','High','Medium','Low'],
      datasets: [{
        data: [sev.critical||0, sev.high||0, sev.medium||0, sev.low||0],
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

  if (chartTypes) chartTypes.destroy();
  var byType = s.byType || {};
  var typeLabels = Object.keys(byType);
  var typeValues = Object.values(byType);
  chartTypes = new Chart(document.getElementById('chart-types').getContext('2d'), {
    type: 'bar',
    data: {
      labels: typeLabels.map(function(l) { return l.replace(/_/g,' '); }),
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

  // OWASP chart
  if (chartOwasp) chartOwasp.destroy();
  var owaspCounts = {};
  (data.components || []).forEach(function(c) {
    var cats = (c.risk && c.risk.owaspCategories) || [];
    cats.forEach(function(cat) {
      var code = cat.split(':')[0].trim();
      owaspCounts[code] = (owaspCounts[code] || 0) + 1;
    });
  });
  var owaspLabels = Object.keys(owaspCounts).sort();
  var owaspValues = owaspLabels.map(function(l) { return owaspCounts[l]; });
  var owaspColors = ['#f85149','#d29922','#58a6ff','#3fb950','#bc8cff','#f0883e','#a5d6ff','#7ee787','#d2a8ff','#ffa657'];
  chartOwasp = new Chart(document.getElementById('chart-owasp').getContext('2d'), {
    type: 'bar',
    data: {
      labels: owaspLabels,
      datasets: [{
        label: 'Findings',
        data: owaspValues,
        backgroundColor: owaspLabels.map(function(l, i) { return owaspColors[i % owaspColors.length]; }),
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      indexAxis: 'y',
      scales: {
        x: { ticks: { color: '#8b949e', stepSize: 1 }, grid: { color: '#30363d' }, beginAtZero: true },
        y: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function populateTypeFilter(data) {
  var sel = document.getElementById('filter-type');
  sel.innerHTML = '<option value="">All Types</option>';
  var types = new Set((data.components || []).map(function(c) { return c.type; }));
  types.forEach(function(t) {
    var opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t.replace(/_/g, ' ');
    sel.appendChild(opt);
  });
}

function populateWorkflowFilter(data) {
  var sel = document.getElementById('filter-workflow');
  sel.innerHTML = '<option value="">All Workflows</option>';
  var wfNames = new Set((data.components || []).map(function(c) {
    return (c.metadata && c.metadata.workflow_name) || (c.location && c.location.filePath) || '';
  }));
  wfNames.forEach(function(n) {
    if (!n) return;
    var opt = document.createElement('option');
    opt.value = n;
    opt.textContent = n;
    sel.appendChild(opt);
  });
}

function renderWorkflowsTable(data) {
  var el = document.getElementById('workflows-table');
  var comps = data.components || [];
  var wfMap = {};
  comps.forEach(function(c) {
    var wfName = (c.metadata && c.metadata.workflow_name) || (c.location && c.location.filePath) || 'unknown';
    if (!wfMap[wfName]) wfMap[wfName] = { name: wfName, trigger: (c.metadata && c.metadata.trigger_type) || '-', components: 0, highestScore: 0, highestSev: 'low' };
    wfMap[wfName].components++;
    var score = (c.risk && c.risk.score) || 0;
    if (score > wfMap[wfName].highestScore) {
      wfMap[wfName].highestScore = score;
      wfMap[wfName].highestSev = (c.risk && c.risk.severity) || 'low';
    }
  });
  var wfs = Object.values(wfMap);
  wfs.sort(function(a, b) { return b.highestScore - a.highestScore; });
  if (wfs.length === 0) {
    el.innerHTML = '<p style="color:var(--text-dim);padding:10px">No workflows scanned.</p>';
    return;
  }
  var html = '<table><thead><tr><th>Workflow</th><th>Trigger</th><th>AI Components</th><th>Highest Risk</th><th>Severity</th></tr></thead><tbody>';
  wfs.forEach(function(wf) {
    html += '<tr class="wf-row" data-wf="' + esc(wf.name) + '" onclick="filterByWorkflow(this.dataset.wf)">';
    html += '<td><strong>' + esc(wf.name) + '</strong></td>';
    html += '<td>' + esc(wf.trigger) + '</td>';
    html += '<td>' + esc(wf.components) + '</td>';
    html += '<td>' + esc(wf.highestScore) + '</td>';
    html += '<td>' + severityBadge(wf.highestSev) + '</td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

function filterByWorkflow(name) {
  document.getElementById('filter-workflow').value = name;
  var data = SCAN_DATA;
  if (data) renderComponents(data);
  document.getElementById('component-table').scrollIntoView({ behavior: 'smooth' });
}

function renderComponents(data) {
  var search = (document.getElementById('filter-search').value || '').toLowerCase();
  var sevFilter = document.getElementById('filter-severity').value;
  var typeFilter = document.getElementById('filter-type').value;
  var wfFilter = document.getElementById('filter-workflow').value;
  var totalComps = (data.components || []).length;
  var comps = (data.components || []).slice();
  if (search) comps = comps.filter(function(c) {
    return c.name.toLowerCase().indexOf(search) !== -1 || (c.provider||'').toLowerCase().indexOf(search) !== -1;
  });
  if (sevFilter) comps = comps.filter(function(c) { return c.risk && c.risk.severity === sevFilter; });
  if (typeFilter) comps = comps.filter(function(c) { return c.type === typeFilter; });
  if (wfFilter) comps = comps.filter(function(c) {
    var wfName = (c.metadata && c.metadata.workflow_name) || (c.location && c.location.filePath) || '';
    return wfName === wfFilter;
  });
  comps.sort(function(a, b) { return (b.risk ? b.risk.score : 0) - (a.risk ? a.risk.score : 0); });
  filteredComponents = comps;

  // Filter counter
  var countEl = document.getElementById('filter-count');
  if (search || sevFilter || typeFilter || wfFilter) {
    countEl.textContent = 'Showing ' + comps.length + ' of ' + totalComps + ' components';
  } else {
    countEl.textContent = totalComps + ' components';
  }

  var el = document.getElementById('component-table');
  if (comps.length === 0) {
    el.innerHTML = '<p style="color:var(--text-dim);padding:10px">No components match the current filters.</p>';
    return;
  }
  var html = '<table><thead><tr><th>Name</th><th>Type</th><th>Provider</th><th>Severity</th><th>Risk Score</th><th>Workflow</th></tr></thead><tbody>';
  comps.forEach(function(c, idx) {
    var sev = (c.risk && c.risk.severity) || 'low';
    var score = (c.risk && c.risk.score) || 0;
    var wfName = (c.metadata && c.metadata.workflow_name) || (c.location && c.location.filePath) || '';
    html += '<tr onclick="showComponentModal(' + idx + ')">';
    html += '<td><strong>' + esc(c.name) + '</strong></td>';
    html += '<td>' + esc((c.type||'').replace(/_/g,' ')) + '</td>';
    html += '<td>' + esc(c.provider||'-') + '</td>';
    html += '<td>' + severityBadge(sev) + '</td>';
    html += '<td>' + esc(score) + '</td>';
    html += '<td title="' + esc(wfName) + '">' + esc(wfName) + '</td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

function showComponentModal(idx) {
  var c = filteredComponents[idx];
  if (!c) return;
  var sev = (c.risk && c.risk.severity) || 'low';
  var score = (c.risk && c.risk.score) || 0;
  var fp = (c.location && c.location.filePath) || '-';
  var owaspCats = (c.risk && c.risk.owaspCategories && c.risk.owaspCategories.length > 0)
    ? c.risk.owaspCategories.map(function(cat) { return '<span class="owasp-tag">' + esc(cat) + '</span>'; }).join(' ')
    : '<span style="color:var(--text-dim)">None</span>';

  var flagsHtml = '';
  var flags = c.flags || [];
  if (flags.length > 0) {
    flagsHtml = '<div class="flag-section"><h4>Risk Findings & Remediation</h4>';
    flags.forEach(function(flag) {
      var entry = REMEDIATION_MAP[flag];
      var flagSev = entry ? entry.severity : 'low';
      flagsHtml += '<div class="flag-card severity-' + esc(flagSev) + '">';
      flagsHtml += '<div class="flag-card-header"><code>' + esc(flag) + '</code>' + severityBadge(flagSev) + '</div>';
      if (entry) {
        flagsHtml += '<p>' + esc(entry.description) + '</p>';
        flagsHtml += '<strong>Remediation</strong><p>' + esc(entry.remediation) + '</p>';
        flagsHtml += '<strong>Guardrail</strong><p>' + esc(entry.guardrail) + '</p>';
        flagsHtml += '<span class="owasp-tag">' + esc(entry.owaspCategory + ': ' + entry.owaspCategoryName) + '</span>';
      } else {
        flagsHtml += '<p>' + esc(flag.replace(/_/g, ' ')) + '</p>';
      }
      flagsHtml += '</div>';
    });
    flagsHtml += '</div>';
  } else {
    flagsHtml = '<div class="flag-section"><h4>Risk Findings & Remediation</h4><p style="color:var(--text-dim)">No risk flags detected for this component.</p></div>';
  }

  var el = document.getElementById('modal-container');
  el.innerHTML = '<div class="modal-overlay" onclick="closeModal(event)">' +
    '<div class="modal" onclick="event.stopPropagation()">' +
    '<button class="modal-close" onclick="closeModal()">&times;</button>' +
    '<h3>' + esc(c.name) + '</h3>' +
    modalRow('Type', (c.type || '').replace(/_/g, ' ')) +
    modalRow('Provider', c.provider || '-') +
    modalRow('Model', c.modelName || '-') +
    modalRow('Version', c.version || '-') +
    modalRow('Severity', severityBadge(sev)) +
    modalRow('Risk Score', String(score)) +
    modalRow('Workflow', fp) +
    modalRow('OWASP Categories', owaspCats) +
    modalRow('Source', c.source || '-') +
    flagsHtml +
    '</div></div>';
}

function modalRow(label, value) {
  return '<div class="modal-row"><div class="modal-label">' + esc(label) + '</div><div class="modal-value">' + (typeof value === 'string' && value.indexOf('<') !== -1 ? value : esc(value)) + '</div></div>';
}

function closeModal(event) {
  if (event && event.target && !event.target.classList.contains('modal-overlay')) return;
  document.getElementById('modal-container').innerHTML = '';
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') document.getElementById('modal-container').innerHTML = '';
});

function downloadBlob(content, filename, mimeType) {
  var blob = new Blob([content], { type: mimeType });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function exportCSV() {
  if (!SCAN_DATA || !SCAN_DATA.components) return;
  var headers = ['Name','Type','Provider','Version','Severity','Risk Score','Workflow','Flags','OWASP Categories','Source'];
  var rows = SCAN_DATA.components.map(function(c) {
    return [
      c.name || '', (c.type || '').replace(/_/g,' '), c.provider || '',
      c.version || '', (c.risk && c.risk.severity) || '', (c.risk && c.risk.score) || 0,
      (c.location && c.location.filePath) || '', (c.flags || []).join('; '),
      (c.risk && c.risk.owaspCategories) ? c.risk.owaspCategories.join('; ') : '', c.source || ''
    ];
  });
  var csv = [headers].concat(rows).map(function(r) {
    return r.map(function(v) { return '"' + String(v).replace(/"/g, '""') + '"'; }).join(',');
  }).join('\\n');
  downloadBlob(csv, 'trusera-scan.csv', 'text/csv');
}

function exportJSON() {
  if (!SCAN_DATA) return;
  downloadBlob(JSON.stringify(SCAN_DATA, null, 2), 'trusera-scan.json', 'application/json');
}

function safeStorage(method, key, val) {
  try { return method === 'get' ? localStorage.getItem(key) : localStorage.setItem(key, val); } catch(e) { return null; }
}
function initTheme() {
  var saved = safeStorage('get', 'trusera-theme');
  if (saved === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
    document.getElementById('theme-toggle').innerHTML = '&#9728;';
  }
}
document.getElementById('theme-toggle').addEventListener('click', function() {
  var isLight = document.documentElement.getAttribute('data-theme') === 'light';
  if (isLight) {
    document.documentElement.removeAttribute('data-theme');
    this.innerHTML = '&#9790;';
    safeStorage('set', 'trusera-theme', 'dark');
  } else {
    document.documentElement.setAttribute('data-theme', 'light');
    this.innerHTML = '&#9728;';
    safeStorage('set', 'trusera-theme', 'light');
  }
});

initTheme();
${password ? 'trySessionRestore();' : 'renderDashboard();'}
<\/script>
</body>
</html>`;
}
