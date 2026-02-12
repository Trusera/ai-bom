import { describe, it, expect, beforeEach } from "vitest";
import { TruseraClient } from "../src/client.js";
import { TruseraLangChainHandler } from "../src/integrations/langchain.js";
import { EventType } from "../src/events.js";

let client: TruseraClient;
let handler: TruseraLangChainHandler;

beforeEach(() => {
  client = new TruseraClient({
    apiKey: "tsk_test123",
    flushInterval: 999999,
  });
  handler = new TruseraLangChainHandler(client);
});

describe("TruseraLangChainHandler", () => {
  describe("LLM tracking", () => {
    it("should track LLM start", () => {
      handler.handleLLMStart(
        { name: "openai" },
        ["What is AI?", "Explain ML"],
        "run-123"
      );

      expect(client.getQueueSize()).toBe(1);
      expect(handler.getPendingEventCount()).toBe(1);
    });

    it("should track LLM end", () => {
      handler.handleLLMStart({ name: "openai" }, ["test"], "run-123");
      handler.handleLLMEnd(
        {
          generations: [[{ text: "Response 1" }], [{ text: "Response 2" }]],
        },
        "run-123"
      );

      expect(client.getQueueSize()).toBe(2); // start + end
      expect(handler.getPendingEventCount()).toBe(0);
    });

    it("should track LLM error", () => {
      handler.handleLLMStart({ name: "openai" }, ["test"], "run-123");
      handler.handleLLMError(new Error("API rate limit"), "run-123");

      expect(client.getQueueSize()).toBe(2); // start + error
      expect(handler.getPendingEventCount()).toBe(0);
    });

    it("should handle multiple concurrent LLM calls", () => {
      handler.handleLLMStart({ name: "openai" }, ["test1"], "run-1");
      handler.handleLLMStart({ name: "anthropic" }, ["test2"], "run-2");

      expect(handler.getPendingEventCount()).toBe(2);

      handler.handleLLMEnd({ generations: [[{ text: "resp1" }]] }, "run-1");
      expect(handler.getPendingEventCount()).toBe(1);

      handler.handleLLMEnd({ generations: [[{ text: "resp2" }]] }, "run-2");
      expect(handler.getPendingEventCount()).toBe(0);
    });

    it("should include metadata and tags", () => {
      handler.handleLLMStart(
        { name: "openai" },
        ["test"],
        "run-123",
        "parent-456",
        { temperature: 0.7 },
        ["production", "user-query"],
        { user_id: "user-789" }
      );

      expect(client.getQueueSize()).toBe(1);
    });
  });

  describe("Tool tracking", () => {
    it("should track tool start", () => {
      handler.handleToolStart({ name: "calculator" }, "2 + 2", "run-123");

      expect(client.getQueueSize()).toBe(1);
      expect(handler.getPendingEventCount()).toBe(1);
    });

    it("should track tool end", () => {
      handler.handleToolStart({ name: "calculator" }, "2 + 2", "run-123");
      handler.handleToolEnd("4", "run-123");

      expect(client.getQueueSize()).toBe(2);
      expect(handler.getPendingEventCount()).toBe(0);
    });

    it("should track tool error", () => {
      handler.handleToolStart({ name: "web_search" }, "query", "run-123");
      handler.handleToolError(new Error("Network timeout"), "run-123");

      expect(client.getQueueSize()).toBe(2);
      expect(handler.getPendingEventCount()).toBe(0);
    });

    it("should track nested tool calls", () => {
      // Parent tool
      handler.handleToolStart({ name: "parent" }, "input", "run-1", undefined);
      // Child tool
      handler.handleToolStart({ name: "child" }, "input", "run-2", "run-1");

      expect(handler.getPendingEventCount()).toBe(2);

      handler.handleToolEnd("child result", "run-2");
      handler.handleToolEnd("parent result", "run-1");

      expect(handler.getPendingEventCount()).toBe(0);
      expect(client.getQueueSize()).toBe(4); // 2 starts + 2 ends
    });
  });

  describe("Chain tracking", () => {
    it("should track chain start", () => {
      handler.handleChainStart(
        { name: "agent_executor" },
        { input: "user query" },
        "run-123"
      );

      expect(client.getQueueSize()).toBe(1);
      expect(handler.getPendingEventCount()).toBe(1);
    });

    it("should track chain end", () => {
      handler.handleChainStart(
        { name: "agent_executor" },
        { input: "query" },
        "run-123"
      );
      handler.handleChainEnd({ output: "result" }, "run-123");

      expect(client.getQueueSize()).toBe(2);
      expect(handler.getPendingEventCount()).toBe(0);
    });

    it("should track chain error", () => {
      handler.handleChainStart(
        { name: "agent_executor" },
        { input: "query" },
        "run-123"
      );
      handler.handleChainError(new Error("Chain failed"), "run-123");

      expect(client.getQueueSize()).toBe(2);
      expect(handler.getPendingEventCount()).toBe(0);
    });

    it("should handle complex nested chains", () => {
      // Root chain
      handler.handleChainStart({ name: "root" }, { input: "test" }, "run-1");

      // Child LLM call
      handler.handleLLMStart({ name: "openai" }, ["prompt"], "run-2", "run-1");

      // Child tool call
      handler.handleToolStart({ name: "search" }, "query", "run-3", "run-1");

      expect(handler.getPendingEventCount()).toBe(3);

      handler.handleLLMEnd({ generations: [[{ text: "result" }]] }, "run-2");
      handler.handleToolEnd("search result", "run-3");
      handler.handleChainEnd({ output: "final" }, "run-1");

      expect(handler.getPendingEventCount()).toBe(0);
      expect(client.getQueueSize()).toBe(6); // 3 starts + 3 ends
    });
  });

  describe("Utility methods", () => {
    it("should clear pending events", () => {
      handler.handleLLMStart({ name: "openai" }, ["test"], "run-1");
      handler.handleToolStart({ name: "tool" }, "input", "run-2");

      expect(handler.getPendingEventCount()).toBe(2);

      handler.clearPendingEvents();

      expect(handler.getPendingEventCount()).toBe(0);
    });

    it("should handle end without start gracefully", () => {
      // Should not throw
      handler.handleLLMEnd({ generations: [[{ text: "result" }]] }, "nonexistent");
      handler.handleToolEnd("result", "nonexistent");
      handler.handleChainEnd({ output: "result" }, "nonexistent");

      expect(client.getQueueSize()).toBe(0);
    });

    it("should handle error without start gracefully", () => {
      // Should not throw
      handler.handleLLMError(new Error("test"), "nonexistent");
      handler.handleToolError(new Error("test"), "nonexistent");
      handler.handleChainError(new Error("test"), "nonexistent");

      expect(client.getQueueSize()).toBe(0);
    });
  });
});
