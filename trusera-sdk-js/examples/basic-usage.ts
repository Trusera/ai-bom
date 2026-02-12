/**
 * Basic usage example for Trusera SDK
 * Demonstrates HTTP interception and event tracking
 */

import { TruseraClient, TruseraInterceptor, EventType, createEvent } from "trusera-sdk";

async function main() {
  // 1. Create a Trusera client
  const client = new TruseraClient({
    apiKey: process.env.TRUSERA_API_KEY || "tsk_your_api_key_here",
    agentId: "demo-agent",
    debug: true, // Enable debug logging
  });

  console.log("✓ Trusera client initialized");

  // 2. Install the HTTP interceptor
  const interceptor = new TruseraInterceptor();
  interceptor.install(client, {
    enforcement: "log", // Options: "log", "warn", "block"
    excludePatterns: [
      "^https://api\\.trusera\\.io/.*", // Don't intercept Trusera API calls
    ],
    debug: true,
  });

  console.log("✓ HTTP interceptor installed");

  // 3. Make some HTTP calls (these will be automatically tracked)
  console.log("\n--- Making HTTP requests (auto-tracked) ---");

  try {
    // GitHub API call
    const githubResponse = await fetch("https://api.github.com/repos/Trusera/ai-bom");
    const githubData = await githubResponse.json();
    console.log(`✓ GitHub API: ${githubData.name} - ${githubData.stargazers_count} stars`);

    // JSONPlaceholder API call
    const todoResponse = await fetch("https://jsonplaceholder.typicode.com/todos/1");
    const todoData = await todoResponse.json();
    console.log(`✓ Todo API: ${todoData.title}`);
  } catch (error) {
    console.error("Request failed:", error);
  }

  // 4. Manually track custom events
  console.log("\n--- Tracking custom events ---");

  client.track(
    createEvent(
      EventType.TOOL_CALL,
      "calculator.add",
      {
        inputs: [2, 2],
        result: 4,
      },
      {
        session_id: "demo-session-123",
      }
    )
  );
  console.log("✓ Tracked TOOL_CALL event");

  client.track(
    createEvent(EventType.LLM_INVOKE, "openai.gpt4", {
      model: "gpt-4",
      prompt_tokens: 50,
      completion_tokens: 100,
      total_tokens: 150,
    })
  );
  console.log("✓ Tracked LLM_INVOKE event");

  client.track(
    createEvent(EventType.DATA_ACCESS, "database.users.select", {
      table: "users",
      operation: "SELECT",
      row_count: 42,
    })
  );
  console.log("✓ Tracked DATA_ACCESS event");

  // 5. Check queue size
  console.log(`\n--- Current queue size: ${client.getQueueSize()} events ---`);

  // 6. Manually flush events (or wait for auto-flush)
  console.log("\n--- Flushing events to Trusera ---");
  await client.flush();
  console.log("✓ Events flushed");

  // 7. Cleanup
  console.log("\n--- Cleanup ---");
  await client.close();
  interceptor.uninstall();
  console.log("✓ Client closed and interceptor removed");

  console.log("\n✓ Demo complete!");
}

main().catch(console.error);
