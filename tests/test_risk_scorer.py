"""Tests for risk scoring engine."""
from ai_bom.models import AIComponent, ComponentType, Severity, SourceLocation
from ai_bom.utils.risk_scorer import score_component


def _make_component(**kwargs):
    defaults = {
        "name": "test",
        "type": ComponentType.llm_provider,
        "location": SourceLocation(file_path="test.py"),
    }
    defaults.update(kwargs)
    return AIComponent(**defaults)


class TestScoreComponent:
    def test_no_flags_returns_zero(self):
        comp = _make_component()
        risk = score_component(comp)
        assert risk.score == 0
        assert risk.severity == Severity.low
        assert risk.factors == []

    def test_hardcoded_api_key(self):
        comp = _make_component(flags=["hardcoded_api_key"])
        risk = score_component(comp)
        assert risk.score == 30
        assert risk.severity == Severity.medium

    def test_shadow_ai(self):
        comp = _make_component(flags=["shadow_ai"])
        risk = score_component(comp)
        assert risk.score == 25
        assert "shadow" in risk.factors[0].lower() or "declared" in risk.factors[0].lower()

    def test_multiple_flags_accumulate(self):
        comp = _make_component(
            flags=["hardcoded_api_key", "shadow_ai", "internet_facing"],
        )
        risk = score_component(comp)
        assert risk.score == 75  # 30 + 25 + 20
        assert risk.severity == Severity.high
        assert len(risk.factors) == 3

    def test_score_capped_at_100(self):
        comp = _make_component(flags=[
            "hardcoded_api_key", "shadow_ai", "internet_facing",
            "multi_agent_no_trust", "no_auth", "deprecated_model"
        ])
        risk = score_component(comp)
        assert risk.score == 100

    def test_critical_severity(self):
        comp = _make_component(flags=[
            "hardcoded_api_key", "shadow_ai", "internet_facing", "no_auth",
        ])
        risk = score_component(comp)
        assert risk.score >= 76
        assert risk.severity == Severity.critical

    def test_deprecated_model_flag(self):
        comp = _make_component(model_name="gpt-3.5-turbo", flags=["deprecated_model"])
        risk = score_component(comp)
        assert risk.score >= 10
        assert any("deprecated" in f.lower() for f in risk.factors)

    def test_n8n_webhook_no_auth(self):
        comp = _make_component(flags=["webhook_no_auth"], source="n8n")
        risk = score_component(comp)
        assert risk.score == 25

    def test_code_http_tools(self):
        comp = _make_component(flags=["code_http_tools"])
        risk = score_component(comp)
        assert risk.score == 30

    def test_unknown_flag_ignored(self):
        comp = _make_component(flags=["unknown_flag_xyz"])
        risk = score_component(comp)
        assert risk.score == 0

    def test_severity_thresholds(self):
        # Low: 0-25
        result = score_component(_make_component(flags=["unpinned_model"]))
        assert result.severity == Severity.low
        # Medium: 26-50
        result = score_component(
            _make_component(flags=["hardcoded_api_key"]),
        )
        assert result.severity == Severity.medium
        # High: 51-75
        result = score_component(
            _make_component(flags=["hardcoded_api_key", "shadow_ai"]),
        )
        assert result.severity == Severity.high
        # Critical: 76-100
        result = score_component(_make_component(flags=[
            "hardcoded_api_key", "shadow_ai",
            "internet_facing", "no_auth",
        ]))
        assert result.severity == Severity.critical
