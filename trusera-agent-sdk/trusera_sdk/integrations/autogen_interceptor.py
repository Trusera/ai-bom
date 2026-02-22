"""Active AutoGen interceptor for Trusera.

Patches ``ConversableAgent._execute_function`` to evaluate Cedar policies
before function call execution.  Detects both ``autogen`` and ``ag2``
import paths.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..cedar import PolicyDecision
from ..enforcement import EnforcementMode
from ..events import Event, EventType
from ..exceptions import PolicyViolationError

logger = logging.getLogger(__name__)

_ConversableAgent: Any = None
AUTOGEN_AVAILABLE = False

try:
    from autogen import ConversableAgent as _ConvAgent  # noqa: N814

    _ConversableAgent = _ConvAgent
    AUTOGEN_AVAILABLE = True
except ImportError:
    try:
        from ag2 import ConversableAgent as _ConvAgent2  # noqa: N814

        _ConversableAgent = _ConvAgent2
        AUTOGEN_AVAILABLE = True
    except ImportError:
        pass


if AUTOGEN_AVAILABLE:

    class TruseraAutoGenInterceptor:
        """Intercepts AutoGen function calls against Cedar policies.

        Example::

            interceptor = TruseraAutoGenInterceptor(
                client=trusera_client,
                policy_cache=cache,
                enforcement="block",
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
            self._orig_execute: Callable[..., Any] | None = None
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
                raise RuntimeError("AutoGen interceptor already installed")

            if not hasattr(_ConversableAgent, "_execute_function"):
                logger.warning("ConversableAgent._execute_function not found; skipping patch")
                return

            self._orig_execute = _ConversableAgent._execute_function
            orig = self._orig_execute
            ref = self

            def _patched_execute(agent_self: Any, func_call: Any, *args: Any, **kwargs: Any) -> Any:
                func_name = "unknown"
                if isinstance(func_call, dict):
                    func_name = func_call.get("name", "unknown")
                elif hasattr(func_call, "name"):
                    func_name = func_call.name

                agent_name = getattr(agent_self, "name", "unknown")
                target = f"{agent_name}/{func_name}"

                allowed, reason = ref._evaluate("function_call", target)
                ref._enforce(allowed, reason, "function_call", target)
                return orig(agent_self, func_call, *args, **kwargs)

            _ConversableAgent._execute_function = _patched_execute  # type: ignore[assignment]
            self._installed = True
            logger.info("TruseraAutoGenInterceptor installed")

        def uninstall(self) -> None:
            if not self._installed:
                raise RuntimeError("AutoGen interceptor not installed")
            if self._orig_execute:
                _ConversableAgent._execute_function = self._orig_execute  # type: ignore[assignment]
            self._installed = False
            logger.info("TruseraAutoGenInterceptor uninstalled")

        def intercept_agent(self, agent: Any) -> None:
            """Wrap all registered functions on an agent for policy evaluation."""
            if not hasattr(agent, "_function_map"):
                return
            for name, func in list(agent._function_map.items()):
                agent._function_map[name] = self._wrap_function(name, func)

        def _wrap_function(self, name: str, func: Callable[..., Any]) -> Callable[..., Any]:
            ref = self

            def wrapper(*args: Any, **kwargs: Any) -> Any:
                allowed, reason = ref._evaluate("function_call", name)
                ref._enforce(allowed, reason, "function_call", name)
                return func(*args, **kwargs)

            wrapper.__name__ = func.__name__ if hasattr(func, "__name__") else name
            return wrapper

        def __enter__(self) -> TruseraAutoGenInterceptor:
            self.install()
            return self

        def __exit__(self, *exc: Any) -> None:
            if self._installed:
                self.uninstall()

else:

    class TruseraAutoGenInterceptor:  # type: ignore[no-redef]
        """Placeholder when autogen/ag2 is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "pyautogen (or ag2) is required for TruseraAutoGenInterceptor. "
                "Install with: pip install trusera-sdk[autogen]"
            )
