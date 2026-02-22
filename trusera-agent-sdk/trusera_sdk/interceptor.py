"""
Active HTTP interceptor backed by Trusera Cedar policy evaluation.

Unlike ``StandaloneInterceptor`` (local-only, httpx-only), ``TruseraInterceptor``
supports **requests**, **httpx**, and **urllib3**, evaluates actions against
API-fetched Cedar policies via ``PolicyCache``, and emits structured
``INTERCEPTION`` / ``POLICY_VIOLATION`` events to the Trusera platform.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from typing import Any, Callable

from .cedar import PolicyDecision
from .enforcement import EnforcementMode
from .events import Event, EventType
from .exceptions import PolicyViolationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional library availability
# ---------------------------------------------------------------------------

try:
    import requests as _requests
    import requests.adapters  # noqa: F401

    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

try:
    import httpx as _httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

try:
    import urllib3 as _urllib3

    _URLLIB3_AVAILABLE = True
except ImportError:
    _URLLIB3_AVAILABLE = False


class TruseraInterceptor:
    """Active HTTP interceptor that evaluates requests against Cedar policies.

    Monkey-patches ``requests.Session.send``, ``httpx.Client.send``,
    ``httpx.AsyncClient.send``, and ``urllib3.HTTPConnectionPool.urlopen``
    to evaluate every outbound HTTP request against Cedar policies fetched
    from the Trusera API (via :class:`~trusera_sdk.policy_cache.PolicyCache`).

    Example::

        from trusera_sdk import TruseraClient, TruseraInterceptor

        client = TruseraClient(api_key="tsk_...")
        interceptor = TruseraInterceptor(
            client=client,
            enforcement="block",
        )
        interceptor.install()

    Or with a context manager::

        with TruseraInterceptor(client=client) as i:
            ...
    """

    def __init__(
        self,
        client: Any | None = None,
        enforcement: str | EnforcementMode = EnforcementMode.LOG,
        policy_cache: Any | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """
        Args:
            client: Optional :class:`~trusera_sdk.client.TruseraClient` for
                    event reporting. If ``None``, violations are only logged.
            enforcement: ``"block"``, ``"warn"``, or ``"log"``.
            policy_cache: Optional :class:`~trusera_sdk.policy_cache.PolicyCache`.
                          If ``None`` a default cache is created when *client*
                          is provided.
            exclude_patterns: Regex patterns for URLs to skip (e.g. Trusera's
                              own API).
        """
        if isinstance(enforcement, str):
            self.enforcement = EnforcementMode.from_string(enforcement)
        else:
            self.enforcement = enforcement

        self._client = client
        self._cache = policy_cache
        self._exclude_res = [re.compile(p) for p in (exclude_patterns or [])]

        # Ensure we never intercept requests to the Trusera API itself
        if client and hasattr(client, "base_url"):
            self._exclude_res.append(re.compile(re.escape(client.base_url)))

        # Original method references for uninstall
        self._orig_requests_send: Callable[..., Any] | None = None
        self._orig_httpx_sync_send: Callable[..., Any] | None = None
        self._orig_httpx_async_send: Callable[..., Any] | None = None
        self._orig_urllib3_urlopen: Callable[..., Any] | None = None

        self._installed = False
        self._event_count = 0

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def _should_intercept(self, url: str) -> bool:
        for pattern in self._exclude_res:
            if pattern.search(url):
                return False
        return True

    def _evaluate(
        self, url: str, method: str, headers: dict[str, str] | None = None
    ) -> tuple[bool, str, str | None]:
        """Evaluate a request against the policy cache.

        Returns:
            (should_allow, reason, policy_id)
        """
        if self._cache is None:
            return True, "No policy cache configured", None

        result = self._cache.evaluate_request(url, method, headers)
        policy_id = None
        if hasattr(result, "matched_rule") and result.matched_rule:
            policy_id = getattr(result.matched_rule, "raw", None)
        return result.decision == PolicyDecision.ALLOW, result.reason, policy_id

    def _enforce(
        self,
        should_allow: bool,
        reason: str,
        method: str,
        url: str,
        policy_id: str | None,
    ) -> None:
        """Apply enforcement mode for a policy decision."""
        if should_allow:
            return

        if self.enforcement == EnforcementMode.BLOCK:
            self._emit_violation(method, url, reason, policy_id)
            raise PolicyViolationError(
                action="http",
                target=f"{method} {url}",
                reason=reason,
                policy_id=policy_id,
            )

        if self.enforcement == EnforcementMode.WARN:
            logger.warning("[POLICY WARN] %s %s: %s", method, url, reason)
            print(
                f"Policy violation (warn mode): {method} {url}\n   Reason: {reason}",
                file=sys.stderr,
            )
            self._emit_violation(method, url, reason, policy_id)

        if self.enforcement == EnforcementMode.LOG:
            logger.info("[POLICY LOG] %s %s: %s", method, url, reason)
            self._emit_violation(method, url, reason, policy_id)

    def _emit_violation(self, method: str, url: str, reason: str, policy_id: str | None) -> None:
        if not self._client:
            return
        event = Event(
            type=EventType.POLICY_VIOLATION,
            name=f"policy_violation_{method.lower()}",
            payload={"method": method, "url": url, "reason": reason},
            metadata={"enforcement": self.enforcement.value, "policy_id": policy_id},
        )
        self._client.track(event)

    def _emit_interception(
        self, method: str, url: str, status_code: int | None, duration_ms: float, allowed: bool
    ) -> None:
        if not self._client:
            return
        self._event_count += 1
        event = Event(
            type=EventType.INTERCEPTION,
            name=f"http_{method.lower()}",
            payload={
                "method": method,
                "url": url,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
            },
            metadata={"allowed": allowed, "enforcement": self.enforcement.value},
        )
        self._client.track(event)

    # ------------------------------------------------------------------
    # requests interception
    # ------------------------------------------------------------------

    def _intercept_requests_send(
        self,
        original: Callable[..., Any],
        session_self: Any,
        request: Any,
        **kwargs: Any,
    ) -> Any:
        url = str(request.url)
        method = request.method or "GET"

        if not self._should_intercept(url):
            return original(session_self, request, **kwargs)

        start = time.time()
        headers_dict = dict(request.headers) if request.headers else None
        allowed, reason, pid = self._evaluate(url, method, headers_dict)
        self._enforce(allowed, reason, method, url, pid)

        response = original(session_self, request, **kwargs)
        duration_ms = (time.time() - start) * 1000
        self._emit_interception(method, url, response.status_code, duration_ms, allowed)
        return response

    # ------------------------------------------------------------------
    # httpx sync interception
    # ------------------------------------------------------------------

    def _intercept_httpx_sync(
        self,
        original: Callable[..., Any],
        client_self: Any,
        request: Any,
        **kwargs: Any,
    ) -> Any:
        url = str(request.url)
        method = request.method

        if not self._should_intercept(url):
            return original(client_self, request, **kwargs)

        start = time.time()
        headers_dict = dict(request.headers) if request.headers else None
        allowed, reason, pid = self._evaluate(url, method, headers_dict)
        self._enforce(allowed, reason, method, url, pid)

        response = original(client_self, request, **kwargs)
        duration_ms = (time.time() - start) * 1000
        self._emit_interception(method, url, response.status_code, duration_ms, allowed)
        return response

    # ------------------------------------------------------------------
    # httpx async interception
    # ------------------------------------------------------------------

    async def _intercept_httpx_async(
        self,
        original: Callable[..., Any],
        client_self: Any,
        request: Any,
        **kwargs: Any,
    ) -> Any:
        url = str(request.url)
        method = request.method

        if not self._should_intercept(url):
            return await original(client_self, request, **kwargs)

        start = time.time()
        headers_dict = dict(request.headers) if request.headers else None
        allowed, reason, pid = self._evaluate(url, method, headers_dict)
        self._enforce(allowed, reason, method, url, pid)

        response = await original(client_self, request, **kwargs)
        duration_ms = (time.time() - start) * 1000
        self._emit_interception(method, url, response.status_code, duration_ms, allowed)
        return response

    # ------------------------------------------------------------------
    # urllib3 interception
    # ------------------------------------------------------------------

    def _intercept_urllib3_urlopen(
        self,
        original: Callable[..., Any],
        pool_self: Any,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        # urllib3 url may be relative; reconstruct from pool
        full_url = url
        if not url.startswith("http"):
            scheme = (
                "https" if hasattr(pool_self, "scheme") and pool_self.scheme == "https" else "http"
            )
            host = getattr(pool_self, "host", "unknown")
            port = getattr(pool_self, "port", None)
            port_str = f":{port}" if port and port not in (80, 443) else ""
            full_url = f"{scheme}://{host}{port_str}{url}"

        if not self._should_intercept(full_url):
            return original(pool_self, method, url, **kwargs)

        start = time.time()
        allowed, reason, pid = self._evaluate(full_url, method)
        self._enforce(allowed, reason, method, full_url, pid)

        response = original(pool_self, method, url, **kwargs)
        duration_ms = (time.time() - start) * 1000
        status = getattr(response, "status", None)
        self._emit_interception(method, full_url, status, duration_ms, allowed)
        return response

    # ------------------------------------------------------------------
    # Install / uninstall
    # ------------------------------------------------------------------

    def install(self) -> None:
        """Monkey-patch HTTP libraries to intercept outbound requests.

        Raises:
            RuntimeError: If already installed.
        """
        if self._installed:
            raise RuntimeError("TruseraInterceptor is already installed")

        # -- requests --
        if _REQUESTS_AVAILABLE:
            self._orig_requests_send = _requests.Session.send
            _orig = self._orig_requests_send
            interceptor = self

            def _req_send(session_self: Any, request: Any, **kwargs: Any) -> Any:
                return interceptor._intercept_requests_send(_orig, session_self, request, **kwargs)

            _requests.Session.send = _req_send  # type: ignore[assignment]

        # -- httpx sync --
        if _HTTPX_AVAILABLE:
            self._orig_httpx_sync_send = _httpx.Client.send
            _orig_sync = self._orig_httpx_sync_send
            interceptor_ref = self

            def _httpx_sync_send(client_self: Any, request: Any, **kwargs: Any) -> Any:
                return interceptor_ref._intercept_httpx_sync(
                    _orig_sync, client_self, request, **kwargs
                )

            _httpx.Client.send = _httpx_sync_send  # type: ignore[method-assign]

            # -- httpx async --
            self._orig_httpx_async_send = _httpx.AsyncClient.send
            _orig_async = self._orig_httpx_async_send

            async def _httpx_async_send(client_self: Any, request: Any, **kwargs: Any) -> Any:
                return await interceptor_ref._intercept_httpx_async(
                    _orig_async, client_self, request, **kwargs
                )

            _httpx.AsyncClient.send = _httpx_async_send  # type: ignore[method-assign]

        # -- urllib3 --
        if _URLLIB3_AVAILABLE:
            self._orig_urllib3_urlopen = _urllib3.HTTPConnectionPool.urlopen
            _orig_u3 = self._orig_urllib3_urlopen
            interceptor_u3 = self

            def _u3_urlopen(pool_self: Any, method: str, url: str, **kwargs: Any) -> Any:
                return interceptor_u3._intercept_urllib3_urlopen(
                    _orig_u3, pool_self, method, url, **kwargs
                )

            _urllib3.HTTPConnectionPool.urlopen = _u3_urlopen  # type: ignore[assignment]

        self._installed = True
        logger.info("TruseraInterceptor installed (enforcement=%s)", self.enforcement.value)

    def uninstall(self) -> None:
        """Restore original HTTP library methods.

        Raises:
            RuntimeError: If not installed.
        """
        if not self._installed:
            raise RuntimeError("TruseraInterceptor is not installed")

        if _REQUESTS_AVAILABLE and self._orig_requests_send:
            _requests.Session.send = self._orig_requests_send  # type: ignore[assignment]
        if _HTTPX_AVAILABLE:
            if self._orig_httpx_sync_send:
                _httpx.Client.send = self._orig_httpx_sync_send  # type: ignore[method-assign]
            if self._orig_httpx_async_send:
                _httpx.AsyncClient.send = self._orig_httpx_async_send  # type: ignore[method-assign]
        if _URLLIB3_AVAILABLE and self._orig_urllib3_urlopen:
            _urllib3.HTTPConnectionPool.urlopen = self._orig_urllib3_urlopen  # type: ignore[assignment]

        self._installed = False
        logger.info("TruseraInterceptor uninstalled (%d events)", self._event_count)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> TruseraInterceptor:
        self.install()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._installed:
            self.uninstall()

    def __repr__(self) -> str:
        return (
            f"TruseraInterceptor(enforcement={self.enforcement.value}, "
            f"installed={self._installed}, events={self._event_count})"
        )
