"""Tests for TruseraLangChainInterceptor."""

import pytest

# LangChain is optional; skip if not installed
langchain = pytest.importorskip("langchain_core")

from trusera_sdk.integrations.langchain_interceptor import (  # noqa: E402
    TruseraLangChainInterceptor,
)


class TestLangChainInterceptorInstall:
    def test_install_uninstall(self, allow_all_cache):
        i = TruseraLangChainInterceptor(policy_cache=allow_all_cache)
        i.install()
        assert i._installed
        i.uninstall()
        assert not i._installed

    def test_install_twice_raises(self, allow_all_cache):
        i = TruseraLangChainInterceptor(policy_cache=allow_all_cache)
        i.install()
        with pytest.raises(RuntimeError):
            i.install()
        i.uninstall()

    def test_context_manager(self, allow_all_cache):
        with TruseraLangChainInterceptor(policy_cache=allow_all_cache) as i:
            assert i._installed
        assert not i._installed


class TestLangChainInterceptorEvaluation:
    def test_deny_blocks(self, deny_all_cache):
        i = TruseraLangChainInterceptor(policy_cache=deny_all_cache, enforcement="block")
        allowed, reason = i._evaluate("tool_call", "search")
        assert allowed is False

    def test_allow_passes(self, allow_all_cache):
        i = TruseraLangChainInterceptor(policy_cache=allow_all_cache, enforcement="block")
        allowed, reason = i._evaluate("tool_call", "search")
        assert allowed is True
