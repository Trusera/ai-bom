"""Trusera SDK for monitoring AI agents."""

from .cedar import CedarEvaluator, EvaluationResult, PolicyAction, PolicyDecision
from .client import TruseraClient
from .decorators import get_default_client, monitor, set_default_client
from .events import Event, EventType
from .standalone import RequestBlockedError, StandaloneInterceptor

__version__ = "0.1.0"

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
]
