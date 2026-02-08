"""CLI integration tests for ai-bom."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ai_bom import __version__
from ai_bom.cli import app

runner = CliRunner()


# ── version command ──────────────────────────────────────────────


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


# ── help ─────────────────────────────────────────────────────────


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scan" in result.output
    assert "demo" in result.output
    assert "version" in result.output


# ── scan command ─────────────────────────────────────────────────


def test_scan_directory():
    demo_path = Path(__file__).parent.parent / "examples" / "demo-project"
    result = runner.invoke(app, ["scan", str(demo_path)])
    assert result.exit_code == 0


def test_scan_single_file():
    demo_file = Path(__file__).parent.parent / "examples" / "demo-project" / "app.py"
    result = runner.invoke(app, ["scan", str(demo_file)])
    assert result.exit_code == 0


def test_scan_nonexistent_path():
    result = runner.invoke(app, ["scan", "/nonexistent/path/that/does/not/exist"])
    assert result.exit_code == 1


def test_scan_cyclonedx_format(tmp_path):
    demo_path = Path(__file__).parent.parent / "examples" / "demo-project"
    out_file = tmp_path / "out.cdx.json"
    result = runner.invoke(
        app, ["scan", str(demo_path), "--format", "cyclonedx", "-o", str(out_file)],
    )
    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert "bomFormat" in data
    assert data["bomFormat"] == "CycloneDX"


def test_scan_sarif_format(tmp_path):
    demo_path = Path(__file__).parent.parent / "examples" / "demo-project"
    out_file = tmp_path / "out.sarif"
    result = runner.invoke(app, ["scan", str(demo_path), "--format", "sarif", "-o", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data.get("$schema") or data.get("version") == "2.1.0"


def test_scan_severity_filter():
    demo_path = Path(__file__).parent.parent / "examples" / "demo-project"
    result = runner.invoke(
        app,
        ["scan", str(demo_path), "--severity", "critical", "--format", "cyclonedx"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    # All remaining components should be critical severity (risk score >= 76)
    for comp in data.get("components", []):
        props = {p["name"]: p["value"] for p in comp.get("properties", [])}
        if "trusera:risk:score" in props:
            assert int(props["trusera:risk:score"]) >= 76


# ── demo command ─────────────────────────────────────────────────


def test_demo_command():
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0


# ── edge cases ───────────────────────────────────────────────────


def test_scan_html_format(tmp_path):
    demo_path = Path(__file__).parent.parent / "examples" / "demo-project"
    out_file = tmp_path / "report.html"
    result = runner.invoke(app, ["scan", str(demo_path), "--format", "html", "-o", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text()
    assert "<html" in content.lower()
