"""OpenAI / Anthropic client interceptor for Trusera.

Provides ``wrap_openai`` and ``wrap_anthropic`` that wrap LLM client
methods to evaluate Cedar policies on tool-use calls in responses and
optionally redact PII from logged prompts.

Unlike the HTTP-level interceptor this is an **explicit opt-in** wrapper
applied to individual client instances rather than a global monkey-patch.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..cedar import PolicyDecision
from ..enforcement import EnforcementMode
from ..events import Event, EventType
from ..exceptions import PolicyViolationError
from ..pii import PIIRedactor

logger = logging.getLogger(__name__)


class TruseraLLMInterceptor:
    """Wraps OpenAI / Anthropic clients for policy enforcement and PII redaction.

    Example::

        from openai import OpenAI
        from trusera_sdk.integrations.llm_interceptor import TruseraLLMInterceptor

        llm_interceptor = TruseraLLMInterceptor(
            client=trusera_client,
            policy_cache=cache,
            enforcement="warn",
            redact_pii=True,
        )

        openai_client = OpenAI()
        llm_interceptor.wrap_openai(openai_client)
    """

    def __init__(
        self,
        client: Any | None = None,
        policy_cache: Any | None = None,
        enforcement: str | EnforcementMode = EnforcementMode.LOG,
        redact_pii: bool = False,
    ) -> None:
        self._client = client
        self._cache = policy_cache
        self.enforcement = (
            EnforcementMode.from_string(enforcement)
            if isinstance(enforcement, str)
            else enforcement
        )
        self._redactor = PIIRedactor() if redact_pii else None

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

    def _log_llm_event(self, provider: str, model: str, messages: Any, response: Any) -> None:
        if not self._client:
            return
        payload: dict[str, Any] = {"provider": provider, "model": model}
        if messages and self._redactor:
            payload["messages"] = self._redactor.redact(_extract_message_texts(messages))
        self._client.track(
            Event(
                type=EventType.LLM_INVOKE,
                name=f"llm_{provider}_{model}",
                payload=payload,
            )
        )

    def _check_tool_use_in_response(self, response: Any) -> None:
        """Evaluate tool_use / function_call blocks in an LLM response."""
        tool_calls = _extract_tool_calls(response)
        for tc in tool_calls:
            allowed, reason = self._evaluate("tool_call", tc)
            self._enforce(allowed, reason, "tool_call", tc)

    # ---- public wrappers ----

    def wrap_openai(self, openai_client: Any) -> None:
        """Wrap an ``openai.OpenAI`` (or ``AsyncOpenAI``) client in-place."""
        if hasattr(openai_client, "chat") and hasattr(openai_client.chat, "completions"):
            self._patch_openai_completions(openai_client.chat.completions)

    def wrap_anthropic(self, anthropic_client: Any) -> None:
        """Wrap an ``anthropic.Anthropic`` (or ``AsyncAnthropic``) client in-place."""
        if hasattr(anthropic_client, "messages"):
            self._patch_anthropic_messages(anthropic_client.messages)

    # ---- openai patching ----

    def _patch_openai_completions(self, completions: Any) -> None:
        ref = self
        orig_create: Callable[..., Any] = completions.create

        def _patched_create(*args: Any, **kwargs: Any) -> Any:
            model = kwargs.get("model", "unknown")
            allowed, reason = ref._evaluate("llm_call", model)
            ref._enforce(allowed, reason, "llm_call", model)

            response = orig_create(*args, **kwargs)
            ref._log_llm_event("openai", model, kwargs.get("messages"), response)
            ref._check_tool_use_in_response(response)
            return response

        completions.create = _patched_create

    # ---- anthropic patching ----

    def _patch_anthropic_messages(self, messages: Any) -> None:
        ref = self
        orig_create: Callable[..., Any] = messages.create

        def _patched_create(*args: Any, **kwargs: Any) -> Any:
            model = kwargs.get("model", "unknown")
            allowed, reason = ref._evaluate("llm_call", model)
            ref._enforce(allowed, reason, "llm_call", model)

            response = orig_create(*args, **kwargs)
            ref._log_llm_event("anthropic", model, kwargs.get("messages"), response)
            ref._check_tool_use_in_response(response)
            return response

        messages.create = _patched_create


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_message_texts(messages: Any) -> list[str]:
    """Pull text content out of an OpenAI/Anthropic messages list."""
    texts: list[str] = []
    if not isinstance(messages, (list, tuple)):
        return texts
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        texts.append(part.get("text", ""))
    return texts


def _extract_tool_calls(response: Any) -> list[str]:
    """Extract tool/function call names from an LLM response object."""
    names: list[str] = []

    # OpenAI: response.choices[0].message.tool_calls
    if hasattr(response, "choices"):
        for choice in response.choices:
            msg = getattr(choice, "message", None)
            if msg and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    fn = getattr(tc, "function", None)
                    if fn:
                        names.append(getattr(fn, "name", "unknown"))

    # Anthropic: response.content[i].type == "tool_use"
    if hasattr(response, "content") and isinstance(response.content, list):
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                names.append(getattr(block, "name", "unknown"))

    return names
