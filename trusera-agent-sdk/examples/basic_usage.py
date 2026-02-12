"""Basic usage example of the Trusera SDK."""

import time
from trusera_sdk import TruseraClient, Event, EventType, monitor, set_default_client


def main() -> None:
    """Run basic usage examples."""
    # Initialize client with context manager
    with TruseraClient(api_key="tsk_your_api_key_here") as client:
        # Register your agent
        agent_id = client.register_agent(
            name="demo-agent",
            framework="custom",
            metadata={"version": "1.0.0", "env": "demo"},
        )

        print(f"Registered agent with ID: {agent_id}")

        # Track a tool call
        client.track(
            Event(
                type=EventType.TOOL_CALL,
                name="web_search",
                payload={
                    "query": "latest AI security news",
                    "filters": {"date": "last_week"},
                },
                metadata={"duration_ms": 250, "results_count": 10},
            )
        )

        # Track an LLM invocation
        client.track(
            Event(
                type=EventType.LLM_INVOKE,
                name="gpt-4",
                payload={
                    "prompt": "Summarize these search results",
                    "response": "Here is a summary...",
                },
                metadata={
                    "model": "gpt-4",
                    "tokens_used": 150,
                    "duration_ms": 500,
                },
            )
        )

        # Track data access
        client.track(
            Event(
                type=EventType.DATA_ACCESS,
                name="user_database_query",
                payload={
                    "query": "SELECT * FROM users WHERE active = true",
                    "rows_returned": 42,
                },
                metadata={"database": "postgres", "duration_ms": 50},
            )
        )

        print("Tracked 3 events")

        # Manual flush to see events sent immediately
        client.flush()
        print("Events flushed to Trusera API")

        time.sleep(1)

    print("Client closed, all events sent")


if __name__ == "__main__":
    main()
