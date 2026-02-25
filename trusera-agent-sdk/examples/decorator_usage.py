"""Example using the @monitor decorator."""

import asyncio
import time

from trusera_sdk import EventType, TruseraClient, monitor, set_default_client

# Initialize client
client = TruseraClient(api_key="tsk_your_api_key_here")
client.register_agent("decorator-demo", "custom")
set_default_client(client)


@monitor(event_type=EventType.TOOL_CALL)
def search_web(query: str, max_results: int = 10) -> list[dict]:
    """Simulate a web search."""
    print(f"Searching for: {query}")
    time.sleep(0.1)  # Simulate API call
    return [{"title": f"Result {i}", "url": f"https://example.com/{i}"} for i in range(max_results)]


@monitor(event_type=EventType.LLM_INVOKE, name="llm_summarize")
def summarize_results(results: list[dict]) -> str:
    """Simulate LLM summarization."""
    print(f"Summarizing {len(results)} results")
    time.sleep(0.2)  # Simulate LLM call
    return f"Summary of {len(results)} search results"


@monitor(event_type=EventType.DATA_ACCESS)
async def async_database_query(user_id: int) -> dict:
    """Simulate async database query."""
    print(f"Querying database for user {user_id}")
    await asyncio.sleep(0.05)  # Simulate async I/O
    return {"id": user_id, "name": "John Doe", "active": True}


@monitor(capture_args=False, capture_result=False)
def process_sensitive_data(api_key: str, secret: str) -> bool:
    """Example with sensitive data - args and results not captured."""
    print("Processing sensitive data (not captured)")
    return True


async def main() -> None:
    """Run decorator examples."""
    print("=== Decorator Usage Examples ===\n")

    # Sync function
    print("1. Sync function with decorator:")
    results = search_web("AI security", max_results=5)
    print(f"   Got {len(results)} results\n")

    # Another sync function
    print("2. Chained functions:")
    summary = summarize_results(results)
    print(f"   {summary}\n")

    # Async function
    print("3. Async function:")
    user = await async_database_query(123)
    print(f"   Retrieved user: {user['name']}\n")

    # Sensitive data
    print("4. Sensitive data (not captured):")
    success = process_sensitive_data("secret_key", "password123")
    print(f"   Processed: {success}\n")

    # Flush and close
    client.flush()
    print("All events tracked and sent to Trusera")

    # Give time for flush
    await asyncio.sleep(0.5)
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
