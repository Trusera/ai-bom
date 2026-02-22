"""Exceptions for Trusera SDK interceptor."""

from __future__ import annotations


class PolicyViolationError(Exception):
    """Raised when an action is blocked by a Cedar policy in enforcement mode 'block'.

    Attributes:
        action: The action type that was blocked (e.g. "http", "tool_call").
        target: The target of the action (e.g. URL, tool name).
        reason: Human-readable reason from policy evaluation.
        policy_id: Optional ID of the matched policy.
    """

    def __init__(
        self,
        action: str,
        target: str,
        reason: str,
        policy_id: str | None = None,
    ) -> None:
        self.action = action
        self.target = target
        self.reason = reason
        self.policy_id = policy_id
        super().__init__(f"Policy violation [{action}] {target}: {reason}")
