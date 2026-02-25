"""Active CrewAI interceptor for Trusera.

Patches ``crewai.tools.BaseTool._run`` to evaluate Cedar policies
before tool execution.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..cedar import PolicyDecision
from ..enforcement import EnforcementMode
from ..events import Event, EventType
from ..exceptions import PolicyViolationError

logger = logging.getLogger(__name__)

try:
    from crewai.tools import BaseTool as CrewBaseTool

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


if CREWAI_AVAILABLE:

    class TruseraCrewAIInterceptor:
        """Intercepts CrewAI tool executions against Cedar policies.

        Example::

            interceptor = TruseraCrewAIInterceptor(
                client=trusera_client,
                policy_cache=cache,
                enforcement="warn",
            )
            interceptor.install()
        """

        def __init__(
            self,
            client: Any | None = None,
            policy_cache: Any | None = None,
            enforcement: str | EnforcementMode = EnforcementMode.LOG,
        ) -> None:
            self._client = client
            self._cache = policy_cache
            self.enforcement = (
                EnforcementMode.from_string(enforcement)
                if isinstance(enforcement, str)
                else enforcement
            )
            self._orig_run: Callable[..., Any] | None = None
            self._installed = False

        def _evaluate(self, action_type: str, target: str) -> tuple[bool, str]:
            if self._cache is None:
                return True, "No policy cache"
            result = self._cache.evaluate_action(action_type, target)
            return result.decision == PolicyDecision.ALLOW, result.reason

        def _enforce(self, allowed: bool, reason: str, action: str, target: str) -> None:
            if allowed:
                return
            if self._client:
                self._client.track(
                    Event(
                        type=EventType.POLICY_VIOLATION,
                        name=f"policy_violation_{action}",
                        payload={"action": action, "target": target, "reason": reason},
                        metadata={"enforcement": self.enforcement.value},
                    )
                )
            if self.enforcement == EnforcementMode.BLOCK:
                raise PolicyViolationError(action=action, target=target, reason=reason)
            if self.enforcement == EnforcementMode.WARN:
                logger.warning("[POLICY WARN] %s %s: %s", action, target, reason)

        def install(self) -> None:
            if self._installed:
                raise RuntimeError("CrewAI interceptor already installed")

            self._orig_run = CrewBaseTool._run
            orig = self._orig_run
            ref = self

            def _patched_run(tool_self: Any, *args: Any, **kwargs: Any) -> Any:
                name = getattr(tool_self, "name", type(tool_self).__name__)
                allowed, reason = ref._evaluate("tool_call", name)
                ref._enforce(allowed, reason, "tool_call", name)
                return orig(tool_self, *args, **kwargs)

            CrewBaseTool._run = _patched_run  # type: ignore[assignment]
            self._installed = True
            logger.info("TruseraCrewAIInterceptor installed")

        def uninstall(self) -> None:
            if not self._installed:
                raise RuntimeError("CrewAI interceptor not installed")
            if self._orig_run:
                CrewBaseTool._run = self._orig_run  # type: ignore[assignment]
            self._installed = False
            logger.info("TruseraCrewAIInterceptor uninstalled")

        def __enter__(self) -> TruseraCrewAIInterceptor:
            self.install()
            return self

        def __exit__(self, *exc: Any) -> None:
            if self._installed:
                self.uninstall()

else:

    class TruseraCrewAIInterceptor:  # type: ignore[no-redef]
        """Placeholder when crewai is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "crewai is required for TruseraCrewAIInterceptor. "
                "Install with: pip install trusera-sdk[crewai]"
            )
