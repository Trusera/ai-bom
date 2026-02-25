"""Tests for PolicyCache."""

import time
from unittest.mock import Mock

from trusera_sdk.cedar import PolicyDecision
from trusera_sdk.policy_cache import PolicyCache


def _make_mock_client(policies=None, fail=False):
    """Build a mock TruseraClient whose _client.get returns policies."""
    mock_http = Mock()
    if fail:
        mock_http.get.side_effect = Exception("API unavailable")
    else:
        resp = Mock()
        resp.status_code = 200
        resp.raise_for_status = Mock()
        resp.json.return_value = {"policies": policies or []}
        mock_http.get.return_value = resp

    client = Mock()
    client._client = mock_http
    client.base_url = "https://api.test.trusera.dev"
    return client


class TestPolicyCacheNoClient:
    def test_no_client_allows_all(self):
        cache = PolicyCache(client=None)
        result = cache.evaluate_request("https://evil.com", "GET")
        assert result.decision == PolicyDecision.ALLOW

    def test_no_client_no_thread(self):
        cache = PolicyCache(client=None)
        assert cache._thread is None


class TestPolicyCacheWithClient:
    def test_eager_load(self):
        client = _make_mock_client(
            policies=[
                {
                    "id": "p1",
                    "name": "Block evil",
                    "cedar_dsl": 'forbid (principal, action == Action::"http", resource) when { request.hostname == "evil.com" };',
                    "enabled": True,
                }
            ]
        )
        cache = PolicyCache(client=client, refresh_interval=999)

        result = cache.evaluate_request("https://evil.com/api", "GET")
        assert result.decision == PolicyDecision.DENY

        result = cache.evaluate_request("https://good.com/api", "GET")
        assert result.decision == PolicyDecision.ALLOW

        cache.stop()

    def test_disabled_policy_ignored(self):
        client = _make_mock_client(
            policies=[
                {
                    "id": "p1",
                    "cedar_dsl": 'forbid (principal, action == Action::"http", resource) when { request.hostname == "evil.com" };',
                    "enabled": False,
                }
            ]
        )
        cache = PolicyCache(client=client, refresh_interval=999)

        result = cache.evaluate_request("https://evil.com/api", "GET")
        assert result.decision == PolicyDecision.ALLOW
        cache.stop()

    def test_hash_based_skip(self):
        """Second refresh with same DSL should not rebuild evaluator."""
        client = _make_mock_client(
            policies=[
                {
                    "id": "p1",
                    "cedar_dsl": 'forbid (principal, action == Action::"http", resource) when { request.hostname == "x.com" };',
                    "enabled": True,
                }
            ]
        )
        cache = PolicyCache(client=client, refresh_interval=999)
        first_eval = cache._evaluator

        cache._refresh_once()  # same DSL
        assert cache._evaluator is first_eval  # same object, not rebuilt
        cache.stop()

    def test_invalidate_forces_refresh(self):
        client = _make_mock_client(
            policies=[
                {
                    "id": "p1",
                    "cedar_dsl": 'forbid (principal, action == Action::"http", resource) when { request.hostname == "a.com" };',
                    "enabled": True,
                }
            ]
        )
        cache = PolicyCache(client=client, refresh_interval=999)
        assert cache._policy_hash != ""

        cache.invalidate()  # clears hash and re-fetches
        assert cache._policy_hash != ""  # re-populated
        cache.stop()

    def test_api_failure_keeps_stale(self):
        client = _make_mock_client(
            policies=[
                {
                    "id": "p1",
                    "cedar_dsl": 'forbid (principal, action == Action::"http", resource) when { request.hostname == "evil.com" };',
                    "enabled": True,
                }
            ]
        )
        cache = PolicyCache(client=client, refresh_interval=999, stale_ttl=300)

        # First load succeeds
        result = cache.evaluate_request("https://evil.com/api", "GET")
        assert result.decision == PolicyDecision.DENY

        # Simulate API failure
        client._client.get.side_effect = Exception("down")
        cache._refresh_once()  # fails silently

        # Stale evaluator still works
        result = cache.evaluate_request("https://evil.com/api", "GET")
        assert result.decision == PolicyDecision.DENY
        cache.stop()

    def test_stale_ttl_exceeded_fails_open(self):
        client = _make_mock_client(
            policies=[
                {
                    "id": "p1",
                    "cedar_dsl": 'forbid (principal, action == Action::"http", resource) when { request.hostname == "evil.com" };',
                    "enabled": True,
                }
            ]
        )
        cache = PolicyCache(client=client, refresh_interval=999, stale_ttl=0.1)

        result = cache.evaluate_request("https://evil.com/api", "GET")
        assert result.decision == PolicyDecision.DENY

        # Wait past stale TTL
        time.sleep(0.2)

        result = cache.evaluate_request("https://evil.com/api", "GET")
        assert result.decision == PolicyDecision.ALLOW
        assert "stale" in result.reason.lower()
        cache.stop()

    def test_evaluate_action(self):
        cache = PolicyCache(client=None)
        result = cache.evaluate_action("tool_call", "search")
        assert result.decision == PolicyDecision.ALLOW
