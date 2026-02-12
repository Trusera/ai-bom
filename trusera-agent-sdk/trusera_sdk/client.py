"""Main client for interacting with the Trusera API."""

import atexit
import logging
import threading
import time
from queue import Empty, Queue
from typing import Any, Optional

import httpx

from .events import Event

logger = logging.getLogger(__name__)


class TruseraClient:
    """
    Client for sending AI agent events to Trusera.

    The client maintains an in-memory queue and flushes events in batches
    to the Trusera API on a background thread.

    Example:
        >>> client = TruseraClient(api_key="tsk_...")
        >>> agent_id = client.register_agent(name="my-agent", framework="langchain")
        >>> client.set_agent_id(agent_id)
        >>> client.track(Event(type=EventType.TOOL_CALL, name="search"))
        >>> client.close()
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.trusera.dev",
        flush_interval: float = 5.0,
        batch_size: int = 100,
        timeout: float = 10.0,
    ) -> None:
        """
        Initialize the Trusera client.

        Args:
            api_key: Trusera API key (starts with 'tsk_')
            base_url: Base URL for the Trusera API
            flush_interval: Seconds between automatic flushes
            batch_size: Maximum events per batch
            timeout: HTTP request timeout in seconds
        """
        if not api_key.startswith("tsk_"):
            logger.warning("API key should start with 'tsk_' prefix")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.flush_interval = flush_interval
        self.batch_size = batch_size
        self.timeout = timeout

        self._queue: Queue[Event] = Queue()
        self._agent_id: Optional[str] = None
        self._shutdown = threading.Event()
        self._lock = threading.Lock()

        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "trusera-sdk-python/0.1.0",
            },
            timeout=self.timeout,
        )

        # Start background flush thread
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        # Register cleanup on exit
        atexit.register(self.close)

    def set_agent_id(self, agent_id: str) -> None:
        """Set the agent ID for this client."""
        with self._lock:
            self._agent_id = agent_id
            logger.info(f"Agent ID set to: {agent_id}")

    def register_agent(
        self, name: str, framework: str, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Register a new agent with Trusera.

        Args:
            name: Agent name
            framework: Framework name (e.g., "langchain", "crewai", "autogen")
            metadata: Additional agent metadata

        Returns:
            The created agent ID

        Raises:
            httpx.HTTPError: If the API request fails
        """
        payload = {
            "name": name,
            "framework": framework,
            "metadata": metadata or {},
        }

        try:
            response = self._client.post(f"{self.base_url}/api/v1/agents", json=payload)
            response.raise_for_status()
            data = response.json()
            agent_id = data["id"]
            self.set_agent_id(agent_id)
            logger.info(f"Registered agent '{name}' with ID: {agent_id}")
            return agent_id
        except httpx.HTTPError as e:
            logger.error(f"Failed to register agent: {e}")
            raise

    def track(self, event: Event) -> None:
        """
        Add an event to the queue for sending to Trusera.

        Args:
            event: The event to track
        """
        if self._shutdown.is_set():
            logger.warning("Client is shutting down, event will not be tracked")
            return

        self._queue.put(event)
        logger.debug(f"Queued event: {event.type.value} - {event.name}")

        # Flush immediately if we've hit the batch size
        if self._queue.qsize() >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """
        Immediately flush all queued events to the Trusera API.

        This is called automatically on a background thread, but can be
        called manually if you need to ensure events are sent immediately.
        """
        if not self._agent_id:
            logger.warning("No agent ID set, cannot flush events")
            return

        events_to_send: list[Event] = []

        # Drain the queue up to batch_size
        while len(events_to_send) < self.batch_size:
            try:
                event = self._queue.get_nowait()
                events_to_send.append(event)
            except Empty:
                break

        if not events_to_send:
            return

        # Send batch to API
        payload = {
            "events": [event.to_dict() for event in events_to_send],
        }

        try:
            url = f"{self.base_url}/api/v1/agents/{self._agent_id}/events"
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Flushed {len(events_to_send)} events to Trusera")
        except httpx.HTTPError as e:
            logger.error(f"Failed to flush events: {e}")
            # Re-queue events on failure (simple strategy)
            for event in events_to_send:
                self._queue.put(event)

    def _flush_loop(self) -> None:
        """Background thread that periodically flushes events."""
        while not self._shutdown.is_set():
            time.sleep(self.flush_interval)
            if not self._shutdown.is_set():
                self.flush()

    def close(self) -> None:
        """
        Close the client and flush any remaining events.

        This is called automatically on exit via atexit.
        """
        if self._shutdown.is_set():
            return

        logger.info("Closing Trusera client...")
        self._shutdown.set()

        # Wait for flush thread to exit
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=self.flush_interval + 1)

        # Final flush
        self.flush()

        # Close HTTP client
        self._client.close()
        logger.info("Trusera client closed")

    def __enter__(self) -> "TruseraClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()
