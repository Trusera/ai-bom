"""Example using Trusera with LangChain.

This example requires langchain-core to be installed:
    pip install trusera-sdk[langchain]
"""

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.messages import HumanMessage, SystemMessage
    from trusera_sdk import TruseraClient
    from trusera_sdk.integrations.langchain import TruseraCallbackHandler

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("LangChain not available. Install with: pip install trusera-sdk[langchain]")


def main() -> None:
    """Run LangChain integration example."""
    if not LANGCHAIN_AVAILABLE:
        return

    print("=== LangChain Integration Example ===\n")

    # Initialize Trusera client
    client = TruseraClient(api_key="tsk_your_api_key_here")
    agent_id = client.register_agent("langchain-demo", "langchain")
    print(f"Registered agent: {agent_id}\n")

    # Create callback handler
    handler = TruseraCallbackHandler(client)

    # Example: Using with LangChain's ChatOpenAI (conceptual)
    print("In a real scenario, you would use the handler with LangChain:")
    print("""
    from langchain.chat_models import ChatOpenAI
    from langchain.agents import initialize_agent, Tool

    # Initialize with Trusera callback
    llm = ChatOpenAI(callbacks=[handler])

    # Define tools
    tools = [
        Tool(
            name="Search",
            func=search_function,
            description="Search the web"
        )
    ]

    # Create agent
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        callbacks=[handler]  # All interactions tracked
    )

    # Run agent - all LLM calls and tool usage tracked automatically
    result = agent.run("What are the latest AI security trends?")
    """)

    print("\nAll LLM invocations, tool calls, and chain executions")
    print("would be automatically tracked and sent to Trusera.")

    # Cleanup
    client.flush()
    client.close()
    print("\nEvents sent to Trusera API")


if __name__ == "__main__":
    main()
