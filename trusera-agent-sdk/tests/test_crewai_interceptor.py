"""Tests for TruseraCrewAIInterceptor."""

import pytest

# CrewAI is optional; skip if not installed
crewai = pytest.importorskip("crewai")

from trusera_sdk.integrations.crewai_interceptor import TruseraCrewAIInterceptor  # noqa: E402


class TestCrewAIInterceptorInstall:
    def test_install_uninstall(self, allow_all_cache):
        i = TruseraCrewAIInterceptor(policy_cache=allow_all_cache)
        i.install()
        assert i._installed
        i.uninstall()
        assert not i._installed

    def test_install_twice_raises(self, allow_all_cache):
        i = TruseraCrewAIInterceptor(policy_cache=allow_all_cache)
        i.install()
        with pytest.raises(RuntimeError):
            i.install()
        i.uninstall()


class TestCrewAIInterceptorEvaluation:
    def test_deny_blocks(self, deny_all_cache):
        i = TruseraCrewAIInterceptor(policy_cache=deny_all_cache, enforcement="block")
        allowed, reason = i._evaluate("tool_call", "search")
        assert allowed is False
