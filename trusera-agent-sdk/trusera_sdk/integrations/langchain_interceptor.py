"""Active LangChain interceptor for Trusera.

Monkey-patches ``BaseTool._run`` / ``_arun`` and ``BaseLLM._generate`` /
``BaseChatModel._generate`` to evaluate Cedar policies **before** execution.
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
    from langchain_core.language_models import BaseChatModel, BaseLLM
    from langchain_core.tools import BaseTool

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


if LANGCHAIN_AVAILABLE:

    class TruseraLangChainInterceptor:
        """Intercepts LangChain tool and LLM calls against Cedar policies.

        Example::

            from trusera_sdk.integrations.langchain_interceptor import (
                TruseraLangChainInterceptor,
            )

            interceptor = TruseraLangChainInterceptor(
                client=trusera_client,
                policy_cache=cache,
                enforcement="block",
            )
            interceptor.install()
            # ... LangChain code runs with policy enforcement ...
            interceptor.uninstall()
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

            self._orig_tool_run: Callable[..., Any] | None = None
            self._orig_tool_arun: Callable[..., Any] | None = None
            self._orig_llm_generate: Callable[..., Any] | None = None
            self._orig_chat_generate: Callable[..., Any] | None = None
            self._installed = False

        # ---- evaluation helpers ----

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

        # ---- install / uninstall ----

        def install(self) -> None:
            if self._installed:
                raise RuntimeError("LangChain interceptor already installed")

            # -- BaseTool._run --
            self._orig_tool_run = BaseTool._run
            orig_run = self._orig_tool_run
            ref = self

            def _patched_run(tool_self: Any, *args: Any, **kwargs: Any) -> Any:
                name = getattr(tool_self, "name", type(tool_self).__name__)
                allowed, reason = ref._evaluate("tool_call", name)
                ref._enforce(allowed, reason, "tool_call", name)
                return orig_run(tool_self, *args, **kwargs)

            BaseTool._run = _patched_run  # type: ignore[assignment]

            # -- BaseTool._arun --
            self._orig_tool_arun = BaseTool._arun
            orig_arun = self._orig_tool_arun

            async def _patched_arun(tool_self: Any, *args: Any, **kwargs: Any) -> Any:
                name = getattr(tool_self, "name", type(tool_self).__name__)
                allowed, reason = ref._evaluate("tool_call", name)
                ref._enforce(allowed, reason, "tool_call", name)
                return await orig_arun(tool_self, *args, **kwargs)

            BaseTool._arun = _patched_arun  # type: ignore[assignment]

            # -- BaseLLM._generate --
            self._orig_llm_generate = BaseLLM._generate
            orig_llm_gen = self._orig_llm_generate

            def _patched_llm_gen(llm_self: Any, *args: Any, **kwargs: Any) -> Any:
                model = getattr(llm_self, "model_name", type(llm_self).__name__)
                allowed, reason = ref._evaluate("llm_call", model)
                ref._enforce(allowed, reason, "llm_call", model)
                return orig_llm_gen(llm_self, *args, **kwargs)

            BaseLLM._generate = _patched_llm_gen  # type: ignore[assignment]

            # -- BaseChatModel._generate --
            self._orig_chat_generate = BaseChatModel._generate
            orig_chat_gen = self._orig_chat_generate

            def _patched_chat_gen(chat_self: Any, *args: Any, **kwargs: Any) -> Any:
                model = getattr(chat_self, "model_name", type(chat_self).__name__)
                allowed, reason = ref._evaluate("llm_call", model)
                ref._enforce(allowed, reason, "llm_call", model)
                return orig_chat_gen(chat_self, *args, **kwargs)

            BaseChatModel._generate = _patched_chat_gen  # type: ignore[assignment]

            self._installed = True
            logger.info("TruseraLangChainInterceptor installed")

        def uninstall(self) -> None:
            if not self._installed:
                raise RuntimeError("LangChain interceptor not installed")
            if self._orig_tool_run:
                BaseTool._run = self._orig_tool_run  # type: ignore[assignment]
            if self._orig_tool_arun:
                BaseTool._arun = self._orig_tool_arun  # type: ignore[assignment]
            if self._orig_llm_generate:
                BaseLLM._generate = self._orig_llm_generate  # type: ignore[assignment]
            if self._orig_chat_generate:
                BaseChatModel._generate = self._orig_chat_generate  # type: ignore[assignment]
            self._installed = False
            logger.info("TruseraLangChainInterceptor uninstalled")

        def __enter__(self) -> TruseraLangChainInterceptor:
            self.install()
            return self

        def __exit__(self, *exc: Any) -> None:
            if self._installed:
                self.uninstall()

else:

    class TruseraLangChainInterceptor:  # type: ignore[no-redef]
        """Placeholder when langchain-core is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "langchain-core is required for TruseraLangChainInterceptor. "
                "Install with: pip install trusera-sdk[langchain]"
            )
