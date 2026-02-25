"""Main client for interacting with the Trusera API."""

import atexit
import logging
import os
import socket
import sys
import threading
import time
from queue import Empty, Queue
from typing import Any, Optional

import httpx

from .events import Event

logger = logging.getLogger(__name__)

_SDK_VERSION = "1.0.0"


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

    Fleet auto-registration:
        >>> client = TruseraClient(api_key="tsk_...", auto_register=True)
        >>> # Automatically registers with fleet and sends heartbeats every 60s
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.trusera.dev",
        flush_interval: float = 5.0,
        batch_size: int = 100,
        timeout: float = 10.0,
        auto_register: bool = False,
        agent_name: Optional[str] = None,
        agent_type: Optional[str] = None,
        environment: Optional[str] = None,
        heartbeat_interval: float = 60.0,
    ) -> None:
        """
        Initialize the Trusera client.

        Args:
            api_key: Trusera API key (starts with 'tsk_')
            base_url: Base URL for the Trusera API
            flush_interval: Seconds between automatic flushes
            batch_size: Maximum events per batch
            timeout: HTTP request timeout in seconds
            auto_register: Auto-register with fleet discovery on startup.
                Overridden by TRUSERA_AUTO_REGISTER env var.
            agent_name: Name for fleet registration (defaults to hostname)
            agent_type: Agent type for fleet registration (e.g. "langchain", "crewai")
            environment: Deployment environment (defaults to TRUSERA_ENVIRONMENT env var)
            heartbeat_interval: Seconds between fleet heartbeats (default 60).
                Overridden by TRUSERA_HEARTBEAT_INTERVAL env var.
        """
        if not api_key.startswith("tsk_"):
            logger.warning("API key should start with 'tsk_' prefix")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.flush_interval = flush_interval
        self.batch_size = batch_size
        self.timeout = timeout

        # Fleet auto-registration config
        env_auto = os.environ.get("TRUSERA_AUTO_REGISTER", "").lower()
        if env_auto in ("true", "1", "yes"):
            auto_register = True
        elif env_auto in ("false", "0", "no"):
            auto_register = False
        self._auto_register = auto_register
        self._agent_name = agent_name or os.environ.get("TRUSERA_AGENT_NAME") or socket.gethostname()
        self._agent_type = agent_type or os.environ.get("TRUSERA_AGENT_TYPE", "")
        self._environment = environment or os.environ.get("TRUSERA_ENVIRONMENT", "")
        env_hb = os.environ.get("TRUSERA_HEARTBEAT_INTERVAL")
        self._heartbeat_interval = float(env_hb) if env_hb else heartbeat_interval

        self._queue: Queue[Event] = Queue()
        self._agent_id: Optional[str] = None
        self._fleet_agent_id: Optional[str] = None
        self._shutdown = threading.Event()
        self._lock = threading.Lock()

        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"trusera-sdk-python/{_SDK_VERSION}",
            },
            timeout=self.timeout,
        )

        # Fleet auto-registration (before starting other threads)
        if self._auto_register:
            self._register_with_fleet()

        # Start background flush thread
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        # Start heartbeat thread if fleet registration succeeded
        self._heartbeat_thread: Optional[threading.Thread] = None
        if self._fleet_agent_id:
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._heartbeat_thread.start()

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

    # -- Fleet auto-registration --------------------------------------------------

    def _get_process_info(self) -> dict[str, Any]:
        """Collect current process information."""
        info: dict[str, Any] = {
            "pid": os.getpid(),
            "argv": sys.argv[:10],  # truncate very long arg lists
            "python_version": sys.version,
        }
        try:
            import getpass
            info["user"] = getpass.getuser()
        except Exception:
            pass
        try:
            info["ppid"] = os.getppid()
        except AttributeError:
            pass
        return info

    def _get_network_info(self) -> dict[str, Any]:
        """Collect network information from the host."""
        info: dict[str, Any] = {
            "hostname": socket.gethostname(),
        }
        try:
            info["fqdn"] = socket.getfqdn()
        except Exception:
            pass
        try:
            info["ip"] = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            pass
        return info

    def _register_with_fleet(self) -> None:
        """Register this SDK instance with the fleet discovery API.

        On failure, logs a warning and continues — fleet registration must
        never block normal SDK operation.
        """
        payload: dict[str, Any] = {
            "name": self._agent_name,
            "discovery_method": "sdk",
            "sdk_version": _SDK_VERSION,
            "hostname": socket.gethostname(),
            "process_info": self._get_process_info(),
            "network_info": self._get_network_info(),
        }
        if self._agent_type:
            payload["framework"] = self._agent_type
        if self._environment:
            payload["environment"] = self._environment

        try:
            response = self._client.post(f"{self.base_url}/api/v1/fleet/register", json=payload)
            response.raise_for_status()
            data = response.json()
            agent_data = data.get("data", data)
            fleet_id = agent_data.get("id")
            if fleet_id:
                self._fleet_agent_id = str(fleet_id)
                logger.info("Fleet auto-register succeeded (id=%s)", self._fleet_agent_id)
            else:
                logger.warning("Fleet register response missing agent id")
        except httpx.HTTPError as exc:
            logger.warning("Fleet auto-register failed (will continue without): %s", exc)
        except Exception as exc:
            logger.warning("Fleet auto-register unexpected error (will continue without): %s", exc)

    def _heartbeat_loop(self) -> None:
        """Background thread that sends periodic heartbeats to the fleet API."""
        while not self._shutdown.is_set():
            self._shutdown.wait(timeout=self._heartbeat_interval)
            if self._shutdown.is_set():
                break
            if not self._fleet_agent_id:
                break
            try:
                payload = {
                    "process_info": self._get_process_info(),
                    "network_info": self._get_network_info(),
                }
                url = f"{self.base_url}/api/v1/fleet/{self._fleet_agent_id}/heartbeat"
                response = self._client.post(url, json=payload)
                response.raise_for_status()
                logger.debug("Fleet heartbeat sent for agent %s", self._fleet_agent_id)
            except httpx.HTTPError as exc:
                logger.warning("Fleet heartbeat failed: %s", exc)
            except Exception as exc:
                logger.warning("Fleet heartbeat unexpected error: %s", exc)

    # -- Lifecycle ----------------------------------------------------------------

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

        # Wait for heartbeat thread to exit
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=self._heartbeat_interval + 1)

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
