"""
Example usage of the StandaloneInterceptor for local HTTP monitoring and policy enforcement.

This example demonstrates how to use the standalone interceptor without
connecting to the Trusera platform. Useful for:
- Local development and testing
- Air-gapped environments
- Proof-of-concept deployments
- CI/CD pipeline integration
"""

import httpx

from trusera_sdk import RequestBlockedError, StandaloneInterceptor


def example_basic_usage():
    """Basic usage with logging only."""
    print("\n=== Basic Usage (log mode) ===")

    # Create interceptor with log file
    interceptor = StandaloneInterceptor(
        enforcement="log",
        log_file="agent-events.jsonl",
    )

    # Install the interceptor
    interceptor.install()

    try:
        # Make some HTTP requests - they will be logged
        client = httpx.Client()
        response = client.get("https://httpbin.org/get")
        print(f"Request 1: {response.status_code}")

        response = client.post("https://httpbin.org/post", json={"test": "data"})
        print(f"Request 2: {response.status_code}")

        # Check stats
        stats = interceptor.get_stats()
        print(f"Events logged: {stats['events_logged']}")

    finally:
        # Uninstall when done
        interceptor.uninstall()
        print("Check agent-events.jsonl for logged events")


def example_with_policy():
    """Usage with Cedar policy enforcement."""
    print("\n=== With Policy (block mode) ===")

    # First, create a policy file
    policy_content = """
    // Block requests to DeepSeek API
    forbid (
        principal,
        action == Action::"http",
        resource
    ) when {
        request.hostname contains "deepseek.com"
    };

    // Block all DELETE requests
    forbid (
        principal,
        action == Action::"http",
        resource
    ) when {
        request.method == "DELETE"
    };

    // Block uploads
    forbid (
        principal,
        action == Action::"http",
        resource
    ) when {
        request.path contains "/upload"
    };
    """

    with open("example-policy.cedar", "w") as f:
        f.write(policy_content)

    # Create interceptor with policy
    interceptor = StandaloneInterceptor(
        policy_file="example-policy.cedar",
        enforcement="block",
        log_file="policy-events.jsonl",
    )

    interceptor.install()

    try:
        client = httpx.Client()

        # This request will be allowed
        print("Making allowed request...")
        response = client.get("https://httpbin.org/get")
        print(f"✓ Allowed: {response.status_code}")

        # This would be blocked (but httpbin doesn't have deepseek.com)
        # Demonstrate with a mock-like scenario
        try:
            # Note: This will fail at network level before our interceptor
            # In real usage, the interceptor would block before the request
            response = client.get("https://api.deepseek.com/v1/chat")
        except RequestBlockedError as e:
            print(f"✗ Blocked: {e}")
        except Exception as e:
            print(f"Network error (would be blocked by policy): {e}")

    finally:
        interceptor.uninstall()


def example_context_manager():
    """Using interceptor as a context manager."""
    print("\n=== Context Manager Usage ===")

    # Using with statement - automatically installs and uninstalls
    with StandaloneInterceptor(
        enforcement="warn",
        log_file="context-events.jsonl",
    ):
        client = httpx.Client()
        resp = client.get("https://httpbin.org/get")
        print(f"Request made: {resp.status_code}")

    # Interceptor is automatically uninstalled here
    print("Interceptor uninstalled automatically")


def example_exclude_patterns():
    """Excluding certain URLs from interception."""
    print("\n=== With Exclude Patterns ===")

    # Exclude internal/trusted APIs from interception
    with StandaloneInterceptor(
        enforcement="log",
        log_file="filtered-events.jsonl",
        exclude_patterns=[
            r"api\.trusera\.",  # Skip Trusera API
            r"localhost:\d+",  # Skip localhost
            r"127\.0\.0\.1",  # Skip loopback
        ],
    ) as iceptor:
        client = httpx.Client()

        # This will be intercepted
        client.get("https://httpbin.org/get")
        print("External API: intercepted and logged")

        # These would be skipped (if they existed)
        # client.get("https://api.trusera.dev/health")
        # client.get("http://localhost:8080/api")

        stats = iceptor.get_stats()
        print(f"Events logged: {stats['events_logged']}")


def example_enforcement_modes():
    """Demonstrating different enforcement modes."""
    print("\n=== Enforcement Modes ===")

    policy_content = """
    forbid (principal, action == Action::"http", resource)
    when { request.path contains "/admin" };
    """

    with open("admin-policy.cedar", "w") as f:
        f.write(policy_content)

    # Mode 1: LOG - logs violations but allows requests
    print("\n1. LOG mode:")
    with StandaloneInterceptor(
        policy_file="admin-policy.cedar",
        enforcement="log",
        log_file="log-mode.jsonl",
    ):
        # Would log but allow the request
        print("LOG mode: violations logged, requests allowed")

    # Mode 2: WARN - prints warnings and allows requests
    print("\n2. WARN mode:")
    with StandaloneInterceptor(
        policy_file="admin-policy.cedar",
        enforcement="warn",
    ):
        # Would print warning but allow the request
        print("WARN mode: warnings printed, requests allowed")

    # Mode 3: BLOCK - raises exception and blocks requests
    print("\n3. BLOCK mode:")
    with StandaloneInterceptor(
        policy_file="admin-policy.cedar",
        enforcement="block",
    ):
        print("BLOCK mode: violations raise RequestBlockedError")


if __name__ == "__main__":
    print("Trusera StandaloneInterceptor Examples")
    print("=" * 50)

    example_basic_usage()
    example_context_manager()
    example_exclude_patterns()
    example_enforcement_modes()

    # Note: example_with_policy() would require actual blocked domains
    # Uncomment to test with real blocked domains:
    # example_with_policy()

    print("\n" + "=" * 50)
    print("Examples complete!")
    print("\nCheck the generated .jsonl files for logged events:")
    print("  - agent-events.jsonl")
    print("  - context-events.jsonl")
    print("  - filtered-events.jsonl")
    print("  - log-mode.jsonl")
