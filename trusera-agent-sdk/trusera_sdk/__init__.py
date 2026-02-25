"""Trusera SDK for monitoring and intercepting AI agent actions."""

from .cedar import CedarEvaluator, EvaluationResult, PolicyAction, PolicyDecision
from .client import TruseraClient
from .decorators import get_default_client, monitor, set_default_client
from .enforcement import EnforcementMode
from .events import Event, EventType
from .exceptions import PolicyViolationError
from .interceptor import TruseraInterceptor
from .pii import PIIRedactor
from .standalone import RequestBlockedError, StandaloneInterceptor

__version__ = "1.1.0"


def intercept(
    client: TruseraClient | None = None,
    enforcement: str = "log",
    exclude_patterns: list[str] | None = None,
) -> TruseraInterceptor:
    """Convenience function to create and install a :class:`TruseraInterceptor`.

    Returns the interceptor so that it can be used as a context manager or
    uninstalled later.

    Example::

        interceptor = trusera_sdk.intercept(client, enforcement="block")
        # ... agent code ...
        interceptor.uninstall()
    """
    from .policy_cache import PolicyCache

    cache = PolicyCache(client=client) if client else None
    i = TruseraInterceptor(
        client=client,
        enforcement=enforcement,
        policy_cache=cache,
        exclude_patterns=exclude_patterns,
    )
    i.install()
    return i


__all__ = [
    "TruseraClient",
    "Event",
    "EventType",
    "monitor",
    "set_default_client",
    "get_default_client",
    "StandaloneInterceptor",
    "RequestBlockedError",
    "CedarEvaluator",
    "PolicyDecision",
    "PolicyAction",
    "EvaluationResult",
    "TruseraInterceptor",
    "PolicyViolationError",
    "EnforcementMode",
    "PIIRedactor",
    "intercept",
]
