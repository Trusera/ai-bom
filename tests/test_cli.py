"""CLI integration tests for ai-bom."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ai_bom import __version__
from ai_bom.cli import app

runner = CliRunner()

demo_path = Path(__file__).parent.parent / "examples" / "demo-project"


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
    assert result.exit_code == 2  # Operational error


def test_scan_cyclonedx_format(tmp_path):
    demo_path = Path(__file__).parent.parent / "examples" / "demo-project"
    out_file = tmp_path / "out.cdx.json"
    result = runner.invoke(
        app,
        ["scan", str(demo_path), "--format", "cyclonedx", "-o", str(out_file)],
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
    out_file = tmp_path / "report.html"
    result = runner.invoke(app, ["scan", str(demo_path), "--format", "html", "-o", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text()
    assert "<html" in content.lower()


# ── v2.0 feature tests ─────────────────────────────────────────


def test_scan_spdx3_format(tmp_path):
    out_file = tmp_path / "out.spdx.json"
    result = runner.invoke(
        app,
        ["scan", str(demo_path), "--format", "spdx3", "-o", str(out_file)],
    )
    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["type"] == "SpdxDocument"


def test_scan_deep_mode(tmp_path):
    # Create a .py file with a known AI import
    py_file = tmp_path / "app.py"
    py_file.write_text("import openai\nclient = openai.OpenAI()\n")
    out_file = tmp_path / "out.cdx.json"
    result = runner.invoke(
        app,
        ["scan", str(tmp_path), "--deep", "--format", "cyclonedx", "-o", str(out_file)],
    )
    assert result.exit_code == 0
    data = json.loads(out_file.read_text())
    # AST scanner should find the openai import
    names = [c.get("name", "") for c in data.get("components", [])]
    assert any("openai" in n.lower() for n in names)


def test_scan_fail_on_exits_1():
    result = runner.invoke(
        app,
        ["scan", str(demo_path), "--fail-on", "low", "--quiet"],
    )
    # demo-project has low+ severity components
    assert result.exit_code == 1


def test_scan_fail_on_invalid_severity():
    result = runner.invoke(
        app,
        ["scan", str(demo_path), "--fail-on", "bogus", "--quiet"],
    )
    # invalid severity is a no-op warning, should still exit 0
    assert result.exit_code == 0


def test_scan_policy_fail(tmp_path):
    policy_file = tmp_path / "policy.yml"
    policy_file.write_text("max_critical: 0\nmax_high: 0\nmax_risk_score: 1\n")
    result = runner.invoke(
        app,
        ["scan", str(demo_path), "--policy", str(policy_file)],
    )
    assert result.exit_code == 1


def test_scan_policy_missing_file():
    result = runner.invoke(
        app,
        ["scan", str(demo_path), "--policy", "/nonexistent-policy.yml"],
    )
    assert result.exit_code == 1


def test_scan_save_dashboard(tmp_path, monkeypatch):
    # Monkeypatch DB_PATH to a temp location
    monkeypatch.setattr("ai_bom.dashboard.db.DB_PATH", tmp_path / "test.db")
    result = runner.invoke(
        app,
        ["scan", str(demo_path), "--save-dashboard"],
    )
    assert result.exit_code == 0
    assert "Scan saved to dashboard" in result.output


def test_scan_cloud_invalid_provider():
    result = runner.invoke(app, ["scan-cloud", "invalid"])
    assert result.exit_code == 2  # Operational error
    assert "Unknown cloud provider" in result.output


def test_dashboard_command_missing_deps(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("mocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    result = runner.invoke(app, ["dashboard"])
    assert result.exit_code == 2  # Operational error
    assert "not installed" in result.output.lower()


def test_no_color_env_var(monkeypatch):
    """Test that NO_COLOR environment variable disables colors."""
    monkeypatch.setenv("NO_COLOR", "1")
    result = runner.invoke(app, ["scan", str(demo_path), "--format", "cyclonedx"])
    assert result.exit_code == 0
    # The console.no_color flag should be set when NO_COLOR is present


def test_scan_star_message_in_table_format():
    """Test that star message appears in table format."""
    demo_file = Path(__file__).parent.parent / "examples" / "demo-project" / "app.py"
    result = runner.invoke(app, ["scan", str(demo_file), "--format", "table"])
    assert result.exit_code == 0
    assert "Found ai-bom useful?" in result.output
    assert "https://github.com/Trusera/ai-bom" in result.output


def test_scan_no_star_message_in_quiet_mode():
    """Test that star message does not appear in quiet mode."""
    demo_file = Path(__file__).parent.parent / "examples" / "demo-project" / "app.py"
    result = runner.invoke(app, ["scan", str(demo_file), "--quiet"])
    assert result.exit_code == 0
    # Quiet mode should suppress the star message
    assert "Found ai-bom useful?" not in result.output or "https://github.com" not in result.output


def test_scan_no_star_message_in_json_format():
    """Test that star message does not appear in JSON format."""
    demo_file = Path(__file__).parent.parent / "examples" / "demo-project" / "app.py"
    result = runner.invoke(app, ["scan", str(demo_file), "--format", "json"])
    assert result.exit_code == 0
    # JSON format should only contain JSON output, not the star message
    data = json.loads(result.output)
    assert "bomFormat" in data  # Valid CycloneDX JSON
