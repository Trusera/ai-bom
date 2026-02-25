"""Tests for TruseraAutoGenInterceptor."""

import pytest

# AutoGen is optional; skip if not installed
autogen = pytest.importorskip("autogen")

from trusera_sdk.integrations.autogen_interceptor import TruseraAutoGenInterceptor  # noqa: E402


class TestAutoGenInterceptorInstall:
    def test_install_uninstall(self, allow_all_cache):
        i = TruseraAutoGenInterceptor(policy_cache=allow_all_cache)
        i.install()
        assert i._installed
        i.uninstall()
        assert not i._installed

    def test_install_twice_raises(self, allow_all_cache):
        i = TruseraAutoGenInterceptor(policy_cache=allow_all_cache)
        i.install()
        with pytest.raises(RuntimeError):
            i.install()
        i.uninstall()


class TestAutoGenInterceptorEvaluation:
    def test_deny_blocks(self, deny_all_cache):
        i = TruseraAutoGenInterceptor(policy_cache=deny_all_cache, enforcement="block")
        allowed, reason = i._evaluate("function_call", "search")
        assert allowed is False
