"""Self-contained HTML reporter with dark theme."""
from __future__ import annotations

from ai_bom.models import ScanResult
from ai_bom.reporters.base import BaseReporter


class HTMLReporter(BaseReporter):
    """Reporter that generates self-contained HTML with dark theme."""

    def render(self, result: ScanResult) -> str:
        """Render scan result as self-contained HTML.

        Args:
            result: The scan result to render

        Returns:
            Complete HTML document string
        """
        # Build summary stats
        summary = result.summary
        critical_count = summary.by_severity.get("critical", 0)
        high_count = summary.by_severity.get("high", 0)
        medium_count = summary.by_severity.get("medium", 0)
        low_count = summary.by_severity.get("low", 0)

        # Build component rows
        component_rows = []
        for i, comp in enumerate(
            sorted(result.components, key=lambda c: c.risk.score, reverse=True), 1
        ):
            risk_score = comp.risk.score
            severity = comp.risk.severity.value

            # Determine severity class for styling
            if severity == "critical":
                severity_class = "severity-critical"
            elif severity == "high":
                severity_class = "severity-high"
            elif severity == "medium":
                severity_class = "severity-medium"
            else:
                severity_class = "severity-low"

            location = comp.location.file_path
            if comp.location.line_number:
                location += f":{comp.location.line_number}"

            flags_display = ", ".join(comp.flags) if comp.flags else "-"

            component_rows.append(
                f"""
            <tr>
                <td>{i}</td>
                <td>{self._escape_html(comp.name)}</td>
                <td>{self._escape_html(comp.type.value)}</td>
                <td>{self._escape_html(comp.provider)}</td>
                <td class="location">{self._escape_html(location)}</td>
                <td class="{severity_class}">{risk_score}</td>
                <td class="{severity_class}">{severity}</td>
                <td class="flags">{self._escape_html(flags_display)}</td>
            </tr>
            """
            )

        components_table = "".join(component_rows) if component_rows else """
            <tr>
                <td colspan="8" style="text-align: center; color: var(--low);">
                    No AI components detected
                </td>
            </tr>
        """

        # Build n8n section if present
        n8n_section = ""
        if result.n8n_workflows:
            n8n_rows = []
            for wf in result.n8n_workflows:
                n8n_rows.append(
                    f"""
                <tr>
                    <td>{self._escape_html(wf.workflow_name)}</td>
                    <td>{len(wf.nodes)}</td>
                    <td>{self._escape_html(wf.trigger_type)}</td>
                    <td>{len(wf.agent_chains)}</td>
                </tr>
                """
                )
            n8n_section = f"""
            <section class="n8n-section">
                <h2>n8n AI Workflows</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Workflow</th>
                            <th>AI Nodes</th>
                            <th>Trigger</th>
                            <th>Agent Chains</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(n8n_rows)}
                    </tbody>
                </table>
            </section>
            """

        # Calculate risk distribution for bar chart
        total = summary.total_components or 1  # Avoid division by zero
        critical_pct = (critical_count / total) * 100
        high_pct = (high_count / total) * 100
        medium_pct = (medium_count / total) * 100
        low_pct = (low_count / total) * 100

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-BOM Report - {self._escape_html(result.target_path)}</title>
    <style>
        :root {{
            --bg: #1a1a2e;
            --card-bg: #16213e;
            --text: #e0e0e0;
            --accent: #58a6ff;
            --critical: #f85149;
            --high: #d29922;
            --medium: #58a6ff;
            --low: #3fb950;
            --border: #30363d;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                'Noto Sans', Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}

        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem;
            background: var(--card-bg);
            border-radius: 8px;
            border: 1px solid var(--border);
        }}

        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            color: var(--accent);
        }}

        .brand {{
            color: var(--low);
            font-weight: bold;
        }}

        .subtitle {{
            color: #8b949e;
            font-size: 0.9rem;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .summary-card {{
            background: var(--card-bg);
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            text-align: center;
        }}

        .summary-card h3 {{
            font-size: 0.9rem;
            color: #8b949e;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .summary-card .value {{
            font-size: 2rem;
            font-weight: bold;
        }}

        .value.critical {{ color: var(--critical); }}
        .value.high {{ color: var(--high); }}
        .value.medium {{ color: var(--medium); }}
        .value.low {{ color: var(--low); }}

        section {{
            background: var(--card-bg);
            padding: 2rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            margin-bottom: 2rem;
        }}

        h2 {{
            color: var(--accent);
            margin-bottom: 1.5rem;
            font-size: 1.5rem;
        }}

        .risk-bar {{
            background: #0d1117;
            border-radius: 4px;
            overflow: hidden;
            height: 30px;
            display: flex;
            margin-bottom: 1rem;
        }}

        .risk-segment {{
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: bold;
            transition: opacity 0.2s;
        }}

        .risk-segment:hover {{
            opacity: 0.8;
        }}

        .risk-critical {{
            background: var(--critical);
            width: {critical_pct}%;
        }}

        .risk-high {{
            background: var(--high);
            width: {high_pct}%;
        }}

        .risk-medium {{
            background: var(--medium);
            width: {medium_pct}%;
        }}

        .risk-low {{
            background: var(--low);
            width: {low_pct}%;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}

        th {{
            background: #0d1117;
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            position: relative;
        }}

        th:hover {{
            background: #161b22;
        }}

        th.sortable::after {{
            content: ' ⇅';
            color: #8b949e;
            font-size: 0.8rem;
        }}

        td {{
            padding: 0.75rem;
            border-top: 1px solid var(--border);
        }}

        tr:hover {{
            background: rgba(56, 139, 253, 0.1);
        }}

        .location {{
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            color: #8b949e;
        }}

        .flags {{
            font-size: 0.85rem;
            color: var(--high);
        }}

        .severity-critical {{ color: var(--critical); font-weight: bold; }}
        .severity-high {{ color: var(--high); font-weight: bold; }}
        .severity-medium {{ color: var(--medium); }}
        .severity-low {{ color: var(--low); }}

        footer {{
            text-align: center;
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
            color: #8b949e;
            font-size: 0.9rem;
        }}

        footer a {{
            color: var(--accent);
            text-decoration: none;
        }}

        footer a:hover {{
            text-decoration: underline;
        }}

        .n8n-section {{
            background: var(--card-bg);
            padding: 2rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            margin-bottom: 2rem;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}

            .summary-grid {{
                grid-template-columns: 1fr;
            }}

            table {{
                font-size: 0.85rem;
            }}

            th, td {{
                padding: 0.5rem;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>AI-BOM Report</h1>
        <p class="subtitle">Discovery Scanner by <span class="brand">Trusera</span></p>
        <p class="subtitle" style="margin-top: 1rem;">
            Target: <strong>{self._escape_html(result.target_path)}</strong><br>
            Scan Date: {result.scan_timestamp}<br>
            AI-BOM Version: {result.ai_bom_version}
        </p>
    </header>

    <div class="summary-grid">
        <div class="summary-card">
            <h3>Total Components</h3>
            <div class="value">{summary.total_components}</div>
        </div>
        <div class="summary-card">
            <h3>Critical Risk</h3>
            <div class="value critical">{critical_count}</div>
        </div>
        <div class="summary-card">
            <h3>High Risk</h3>
            <div class="value high">{high_count}</div>
        </div>
        <div class="summary-card">
            <h3>Medium Risk</h3>
            <div class="value medium">{medium_count}</div>
        </div>
    </div>

    <section>
        <h2>Risk Distribution</h2>
        <div class="risk-bar">
            <div class="risk-segment risk-critical" title="Critical: {critical_count}">
                {critical_count if critical_count > 0 else ''}
            </div>
            <div class="risk-segment risk-high" title="High: {high_count}">
                {high_count if high_count > 0 else ''}
            </div>
            <div class="risk-segment risk-medium" title="Medium: {medium_count}">
                {medium_count if medium_count > 0 else ''}
            </div>
            <div class="risk-segment risk-low" title="Low: {low_count}">
                {low_count if low_count > 0 else ''}
            </div>
        </div>
        <p style="color: #8b949e; font-size: 0.9rem;">
            Files Scanned: {summary.total_files_scanned} |
            Highest Risk Score: {summary.highest_risk_score}/100
        </p>
    </section>

    {n8n_section}

    <section>
        <h2>AI Components</h2>
        <table id="componentsTable">
            <thead>
                <tr>
                    <th class="sortable" onclick="sortTable(0)">#</th>
                    <th class="sortable" onclick="sortTable(1)">Component</th>
                    <th class="sortable" onclick="sortTable(2)">Type</th>
                    <th class="sortable" onclick="sortTable(3)">Provider</th>
                    <th class="sortable" onclick="sortTable(4)">Location</th>
                    <th class="sortable" onclick="sortTable(5)">Risk Score</th>
                    <th class="sortable" onclick="sortTable(6)">Severity</th>
                    <th class="sortable" onclick="sortTable(7)">Flags</th>
                </tr>
            </thead>
            <tbody>
                {components_table}
            </tbody>
        </table>
    </section>

    <footer>
        <p>
            Generated by <a href="https://github.com/trusera/ai-bom" target="_blank">AI-BOM</a> by
            <a href="https://trusera.dev" target="_blank">Trusera</a>
        </p>
        <p style="margin-top: 0.5rem;">
            Secure agent-to-agent communication with Trusera
        </p>
    </footer>

    <script>
        let sortDirection = {{}};

        function sortTable(columnIndex) {{
            const table = document.getElementById('componentsTable');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            // Toggle sort direction
            sortDirection[columnIndex] = !sortDirection[columnIndex];
            const ascending = sortDirection[columnIndex];

            rows.sort((a, b) => {{
                const aValue = a.cells[columnIndex].textContent.trim();
                const bValue = b.cells[columnIndex].textContent.trim();

                // Numeric sort for # and Risk Score columns
                if (columnIndex === 0 || columnIndex === 5) {{
                    return ascending ?
                        parseInt(aValue) - parseInt(bValue) :
                        parseInt(bValue) - parseInt(aValue);
                }}

                // String sort for other columns
                return ascending ?
                    aValue.localeCompare(bValue) :
                    bValue.localeCompare(aValue);
            }});

            // Re-append sorted rows
            rows.forEach(row => tbody.appendChild(row));
        }}
    </script>
</body>
</html>"""

        return html

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters.

        Args:
            text: Text to escape

        Returns:
            HTML-escaped text
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
