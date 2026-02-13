"""
Standalone HTTP interceptor for AI agents without API key requirements.

This module provides HTTP request interception and policy enforcement that works
without connecting to the Trusera platform. It's designed for local development,
testing, and environments where outbound connections are restricted.

Features:
- Monkey-patches httpx for transparent interception
- Cedar policy evaluation for request filtering
- Local JSONL event logging
- Three enforcement modes: block, warn, log
- Thread-safe operation
- Context manager support
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from .cedar import CedarEvaluator, PolicyDecision

logger = logging.getLogger(__name__)


class RequestBlockedError(Exception):
    """Raised when a request is blocked by policy in enforcement mode 'block'."""

    pass


class StandaloneInterceptor:
    """
    Standalone HTTP interceptor that works without TruseraClient.

    This interceptor monkey-patches httpx to intercept HTTP requests, evaluate them
    against Cedar policies, and log events to a local JSONL file.

    Example:
        >>> interceptor = StandaloneInterceptor(
        ...     policy_file=".cedar/ai-policy.cedar",
        ...     enforcement="block",
        ...     log_file="agent-events.jsonl",
        ... )
        >>> interceptor.install()
        >>> # Your agent code here - all httpx requests will be intercepted
        >>> interceptor.uninstall()

        Or use as context manager:
        >>> with StandaloneInterceptor(policy_file="policy.cedar") as interceptor:
        ...     # Your agent code here
        ...     pass
    """

    def __init__(
        self,
        policy_file: str | None = None,
        enforcement: str = "log",
        log_file: str | None = None,
        exclude_patterns: list[str] | None = None,
        debug: bool = False,
    ) -> None:
        """
        Initialize the standalone interceptor.

        Args:
            policy_file: Path to Cedar policy file (optional, if None allows all)
            enforcement: Enforcement mode - "block", "warn", or "log" (default: "log")
            log_file: Path to JSONL log file (optional)
            exclude_patterns: List of regex patterns for URLs to skip interception
            debug: Enable debug logging

        Raises:
            ValueError: If enforcement mode is invalid
            FileNotFoundError: If policy_file is specified but doesn't exist
        """
        if enforcement not in ("block", "warn", "log"):
            raise ValueError(
                f"Invalid enforcement mode: {enforcement}. Must be 'block', 'warn', or 'log'"
            )

        self.enforcement = enforcement
        self.log_file = Path(log_file) if log_file else None
        self.exclude_patterns = [re.compile(pattern) for pattern in (exclude_patterns or [])]
        self.debug = debug

        # Load Cedar policy if provided
        self.evaluator: CedarEvaluator | None = None
        if policy_file:
            policy_path = Path(policy_file)
            if not policy_path.exists():
                raise FileNotFoundError(f"Policy file not found: {policy_file}")
            self.evaluator = CedarEvaluator.from_file(str(policy_path))
            logger.info(f"Loaded Cedar policy from {policy_file}")

        # Track original methods for uninstall
        self._original_sync_send: Callable[..., Any] | None = None
        self._original_async_send: Callable[..., Any] | None = None
        self._installed = False
        self._lock = threading.Lock()

        # Event counter
        self._event_count = 0

        if self.debug:
            logging.basicConfig(level=logging.DEBUG)

    def _should_intercept(self, url: str) -> bool:
        """
        Check if a URL should be intercepted based on exclude patterns.

        Args:
            url: The request URL

        Returns:
            True if the request should be intercepted
        """
        for pattern in self.exclude_patterns:
            if pattern.search(url):
                if self.debug:
                    logger.debug(f"Skipping interception (excluded): {url}")
                return False
        return True

    def _log_event(
        self,
        method: str,
        url: str,
        status_code: int | None,
        duration_ms: float,
        policy_decision: str,
        enforcement_action: str,
        error: str | None = None,
    ) -> None:
        """
        Log an intercepted request to JSONL file.

        Args:
            method: HTTP method
            url: Request URL
            status_code: Response status code (None if blocked before request)
            duration_ms: Request duration in milliseconds
            policy_decision: Cedar policy decision (allow/deny)
            enforcement_action: Action taken (allowed/blocked/warned)
            error: Error message if request failed
        """
        if not self.log_file:
            return

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "url": url,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "policy_decision": policy_decision,
            "enforcement_action": enforcement_action,
            "error": error,
        }

        with self._lock:
            try:
                # Ensure parent directory exists
                self.log_file.parent.mkdir(parents=True, exist_ok=True)

                # Append to JSONL file (one JSON object per line)
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event) + "\n")

                self._event_count += 1
                if self.debug:
                    logger.debug(f"Logged event #{self._event_count}: {method} {url}")
            except Exception as e:
                logger.error(f"Failed to log event: {e}")

    def _evaluate_and_enforce(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[bool, str]:
        """
        Evaluate request against policy and enforce decision.

        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers

        Returns:
            Tuple of (should_allow, reason)
        """
        if not self.evaluator:
            return True, "No policy configured"

        result = self.evaluator.evaluate(url, method, headers)

        if result.decision == PolicyDecision.DENY:
            return False, result.reason
        else:
            return True, result.reason

    def _intercept_sync_request(
        self,
        original_send: Callable[..., Any],
        request: httpx.Request,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Intercept synchronous httpx request.

        Args:
            original_send: Original httpx.Client.send method
            request: The HTTP request
            **kwargs: Additional arguments to send()

        Returns:
            HTTP response

        Raises:
            RequestBlockedError: If enforcement is 'block' and policy denies request
        """
        url = str(request.url)
        method = request.method

        if not self._should_intercept(url):
            return original_send(request, **kwargs)

        start_time = time.time()

        # Evaluate policy
        headers_dict = dict(request.headers) if request.headers else None
        should_allow, reason = self._evaluate_and_enforce(method, url, headers_dict)

        if not should_allow:
            duration_ms = (time.time() - start_time) * 1000

            if self.enforcement == "block":
                self._log_event(
                    method=method,
                    url=url,
                    status_code=None,
                    duration_ms=duration_ms,
                    policy_decision="deny",
                    enforcement_action="blocked",
                    error=reason,
                )
                logger.error(f"[BLOCKED] {method} {url}: {reason}")
                raise RequestBlockedError(f"Request blocked by policy: {reason}")

            elif self.enforcement == "warn":
                logger.warning(f"[WARNING] {method} {url}: {reason}")
                print(f"⚠️  Policy violation (warn mode): {method} {url}", file=sys.stderr)
                print(f"   Reason: {reason}", file=sys.stderr)

        # Execute the actual request
        try:
            response = original_send(request, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            enforcement_action = "allowed" if should_allow else "warned"
            policy_decision = "allow" if should_allow else "deny"

            self._log_event(
                method=method,
                url=url,
                status_code=response.status_code,
                duration_ms=duration_ms,
                policy_decision=policy_decision,
                enforcement_action=enforcement_action,
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._log_event(
                method=method,
                url=url,
                status_code=None,
                duration_ms=duration_ms,
                policy_decision="allow" if should_allow else "deny",
                enforcement_action="error",
                error=str(e),
            )
            raise

    async def _intercept_async_request(
        self,
        original_send: Callable[..., Any],
        request: httpx.Request,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Intercept asynchronous httpx request.

        Args:
            original_send: Original httpx.AsyncClient.send method
            request: The HTTP request
            **kwargs: Additional arguments to send()

        Returns:
            HTTP response

        Raises:
            RequestBlockedError: If enforcement is 'block' and policy denies request
        """
        url = str(request.url)
        method = request.method

        if not self._should_intercept(url):
            return await original_send(request, **kwargs)

        start_time = time.time()

        # Evaluate policy
        headers_dict = dict(request.headers) if request.headers else None
        should_allow, reason = self._evaluate_and_enforce(method, url, headers_dict)

        if not should_allow:
            duration_ms = (time.time() - start_time) * 1000

            if self.enforcement == "block":
                self._log_event(
                    method=method,
                    url=url,
                    status_code=None,
                    duration_ms=duration_ms,
                    policy_decision="deny",
                    enforcement_action="blocked",
                    error=reason,
                )
                logger.error(f"[BLOCKED] {method} {url}: {reason}")
                raise RequestBlockedError(f"Request blocked by policy: {reason}")

            elif self.enforcement == "warn":
                logger.warning(f"[WARNING] {method} {url}: {reason}")
                print(f"⚠️  Policy violation (warn mode): {method} {url}", file=sys.stderr)
                print(f"   Reason: {reason}", file=sys.stderr)

        # Execute the actual request
        try:
            response = await original_send(request, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            enforcement_action = "allowed" if should_allow else "warned"
            policy_decision = "allow" if should_allow else "deny"

            self._log_event(
                method=method,
                url=url,
                status_code=response.status_code,
                duration_ms=duration_ms,
                policy_decision=policy_decision,
                enforcement_action=enforcement_action,
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._log_event(
                method=method,
                url=url,
                status_code=None,
                duration_ms=duration_ms,
                policy_decision="allow" if should_allow else "deny",
                enforcement_action="error",
                error=str(e),
            )
            raise

    def install(self) -> None:
        """
        Install the interceptor by monkey-patching httpx.

        This modifies httpx.Client.send and httpx.AsyncClient.send to intercept
        all HTTP requests made through httpx.

        Raises:
            RuntimeError: If interceptor is already installed
        """
        if self._installed:
            raise RuntimeError("Interceptor is already installed")

        # Save original methods
        self._original_sync_send = httpx.Client.send
        self._original_async_send = httpx.AsyncClient.send

        # Create wrapper functions that capture the original methods
        def sync_send_wrapper(
            client_self: httpx.Client,
            request: httpx.Request,
            **kwargs: Any,
        ) -> httpx.Response:
            original = self._original_sync_send.__get__(client_self, httpx.Client)
            return self._intercept_sync_request(original, request, **kwargs)

        async def async_send_wrapper(
            client_self: httpx.AsyncClient,
            request: httpx.Request,
            **kwargs: Any,
        ) -> httpx.Response:
            original = self._original_async_send.__get__(client_self, httpx.AsyncClient)
            return await self._intercept_async_request(original, request, **kwargs)

        # Monkey-patch httpx
        httpx.Client.send = sync_send_wrapper  # type: ignore[method-assign]
        httpx.AsyncClient.send = async_send_wrapper  # type: ignore[method-assign]

        self._installed = True
        logger.info(f"Trusera StandaloneInterceptor installed (enforcement={self.enforcement})")

    def uninstall(self) -> None:
        """
        Uninstall the interceptor and restore original httpx methods.

        Raises:
            RuntimeError: If interceptor is not installed
        """
        if not self._installed:
            raise RuntimeError("Interceptor is not installed")

        # Restore original methods
        if self._original_sync_send:
            httpx.Client.send = self._original_sync_send  # type: ignore[method-assign]
        if self._original_async_send:
            httpx.AsyncClient.send = self._original_async_send  # type: ignore[method-assign]

        self._installed = False
        logger.info(
            f"Trusera StandaloneInterceptor uninstalled ({self._event_count} events logged)"
        )

    def get_stats(self) -> dict[str, Any]:
        """
        Get interceptor statistics.

        Returns:
            Dictionary with event count and configuration
        """
        return {
            "events_logged": self._event_count,
            "enforcement": self.enforcement,
            "policy_loaded": self.evaluator is not None,
            "log_file": str(self.log_file) if self.log_file else None,
            "installed": self._installed,
        }

    def __enter__(self) -> StandaloneInterceptor:
        """Context manager entry - installs interceptor."""
        self.install()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - uninstalls interceptor."""
        if self._installed:
            self.uninstall()

    def __repr__(self) -> str:
        """String representation of interceptor."""
        return (
            f"StandaloneInterceptor(enforcement={self.enforcement}, "
            f"policy={'loaded' if self.evaluator else 'none'}, "
            f"events={self._event_count})"
        )
