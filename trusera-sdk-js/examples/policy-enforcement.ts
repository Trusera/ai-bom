/**
 * Policy enforcement example for Trusera SDK
 * Demonstrates different enforcement modes and policy evaluation
 */

import { TruseraClient, TruseraInterceptor } from "trusera-sdk";

async function demonstrateLogMode() {
  console.log("\n=== LOG MODE (silent tracking) ===");

  const client = new TruseraClient({
    apiKey: process.env.TRUSERA_API_KEY || "tsk_demo",
    agentId: "policy-demo-log",
  });

  const interceptor = new TruseraInterceptor();
  interceptor.install(client, {
    enforcement: "log",
  });

  // All requests are allowed, violations are logged silently
  try {
    await fetch("https://api.github.com/repos/test/test");
    console.log("✓ Request completed (log mode - all allowed)");
  } catch (error) {
    console.error("Error:", error.message);
  }

  await client.close();
  interceptor.uninstall();
}

async function demonstrateWarnMode() {
  console.log("\n=== WARN MODE (warnings in console) ===");

  const client = new TruseraClient({
    apiKey: process.env.TRUSERA_API_KEY || "tsk_demo",
    agentId: "policy-demo-warn",
  });

  const interceptor = new TruseraInterceptor();
  interceptor.install(client, {
    enforcement: "warn",
    policyUrl: "https://policy.trusera.io/evaluate", // Set if you have a policy service
  });

  // Requests are allowed but warnings are printed to console
  try {
    await fetch("https://api.stripe.com/v1/customers");
    console.log("✓ Request completed (warn mode - allowed with warning)");
  } catch (error) {
    console.error("Error:", error.message);
  }

  await client.close();
  interceptor.uninstall();
}

async function demonstrateBlockMode() {
  console.log("\n=== BLOCK MODE (strict enforcement) ===");

  const client = new TruseraClient({
    apiKey: process.env.TRUSERA_API_KEY || "tsk_demo",
    agentId: "policy-demo-block",
  });

  const interceptor = new TruseraInterceptor();
  interceptor.install(client, {
    enforcement: "block",
    policyUrl: "https://policy.trusera.io/evaluate",
    debug: true,
  });

  // Requests that violate policy will be blocked
  try {
    await fetch("https://api.stripe.com/v1/charges");
    console.log("✓ Request completed (policy allowed)");
  } catch (error) {
    console.error("✗ Request blocked:", error.message);
  }

  await client.close();
  interceptor.uninstall();
}

async function demonstrateExcludePatterns() {
  console.log("\n=== EXCLUDE PATTERNS (selective interception) ===");

  const client = new TruseraClient({
    apiKey: process.env.TRUSERA_API_KEY || "tsk_demo",
    agentId: "policy-demo-exclude",
  });

  const interceptor = new TruseraInterceptor();
  interceptor.install(client, {
    enforcement: "log",
    excludePatterns: [
      "^https://api\\.trusera\\.io/.*", // Exclude Trusera's own API
      "^http://localhost.*", // Exclude localhost
      "^https://internal\\.company\\.com/.*", // Exclude internal services
    ],
    debug: true,
  });

  console.log("\nRequests to excluded URLs:");
  await fetch("http://localhost:3000/health");
  console.log("✓ localhost request (not tracked)");

  console.log("\nRequests to non-excluded URLs:");
  await fetch("https://api.github.com/users/octocat");
  console.log("✓ GitHub API request (tracked)");

  console.log(`\nEvents tracked: ${client.getQueueSize()}`);

  await client.close();
  interceptor.uninstall();
}

async function main() {
  console.log("==============================================");
  console.log("Trusera SDK - Policy Enforcement Examples");
  console.log("==============================================");

  await demonstrateLogMode();
  await demonstrateWarnMode();
  await demonstrateBlockMode();
  await demonstrateExcludePatterns();

  console.log("\n✓ All examples complete!");
}

main().catch(console.error);
