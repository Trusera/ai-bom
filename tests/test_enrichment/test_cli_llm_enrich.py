"""CLI integration tests for --llm-enrich flag."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ai_bom.cli import app

runner = CliRunner()


def _make_fake_litellm():
    """Create a fake litellm module for testing."""
    mod = ModuleType("litellm")
    mod.completion = MagicMock()  # type: ignore[attr-defined]
    return mod


class TestLLMEnrichCLI:
    def test_llm_enrich_without_litellm_shows_install_hint(self, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("from openai import OpenAI\nclient = OpenAI()\n")

        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__  # type: ignore[union-attr]

        def mock_import(name, *args, **kwargs):
            if name == "litellm":
                raise ImportError("No module named 'litellm'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = runner.invoke(
                app,
                [
                    "scan",
                    str(tmp_path),
                    "--llm-enrich",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code != 0
        assert "LLM enrichment requires litellm" in result.output
        assert "pip install" in result.output

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_llm_enrich_flag_triggers_enrichment(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text(
            "from openai import OpenAI\n"
            "client = OpenAI()\n"
            'response = client.chat.completions.create(model="gpt-4o", messages=[])\n'
        )
        req = tmp_path / "requirements.txt"
        req.write_text("openai>=1.0.0\n")

        mock_llm.return_value = '{"model_name": "gpt-4o", "provider": "OpenAI"}'

        fake_litellm = _make_fake_litellm()
        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            result = runner.invoke(
                app,
                [
                    "scan",
                    str(tmp_path),
                    "--llm-enrich",
                    "--format",
                    "table",
                ],
            )

        assert result.exit_code == 0

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_privacy_warning_for_cloud_model(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("from openai import OpenAI\n")
        req = tmp_path / "requirements.txt"
        req.write_text("openai>=1.0.0\n")
        mock_llm.return_value = '{"model_name": "", "provider": ""}'

        fake_litellm = _make_fake_litellm()
        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            result = runner.invoke(
                app,
                [
                    "scan",
                    str(tmp_path),
                    "--llm-enrich",
                    "--llm-model",
                    "gpt-4o-mini",
                ],
            )

        assert "external API" in result.output or "Warning" in result.output

    @patch("ai_bom.enrichment.llm_enricher._call_llm")
    def test_no_privacy_warning_for_ollama(self, mock_llm, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("from openai import OpenAI\n")
        req = tmp_path / "requirements.txt"
        req.write_text("openai>=1.0.0\n")
        mock_llm.return_value = '{"model_name": "", "provider": ""}'

        fake_litellm = _make_fake_litellm()
        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            result = runner.invoke(
                app,
                [
                    "scan",
                    str(tmp_path),
                    "--llm-enrich",
                    "--llm-model",
                    "ollama/llama3",
                ],
            )

        assert "external API" not in result.output
