import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { TruseraClient } from "../src/client.js";
import { EventType, createEvent } from "../src/events.js";

// Mock fetch globally
const originalFetch = globalThis.fetch;
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("TruseraClient", () => {
  describe("constructor", () => {
    it("should create client with minimal options", () => {
      const client = new TruseraClient({ apiKey: "tsk_test123" });
      expect(client).toBeTruthy();
      expect(client.getQueueSize()).toBe(0);
    });

    it("should create client with all options", () => {
      const client = new TruseraClient({
        apiKey: "tsk_test123",
        baseUrl: "https://custom.api",
        agentId: "agent-123",
        flushInterval: 10000,
        batchSize: 50,
        debug: true,
      });

      expect(client.getAgentId()).toBe("agent-123");
    });

    it("should throw on invalid API key", () => {
      expect(() => {
        new TruseraClient({ apiKey: "invalid_key" });
      }).toThrow("Invalid API key format");
    });
  });

  describe("registerAgent", () => {
    it("should register agent and return ID", async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          agent_id: "agent-456",
          name: "test-agent",
          created_at: "2024-01-01T00:00:00Z",
        }),
      } as Response);

      const client = new TruseraClient({ apiKey: "tsk_test123" });
      const agentId = await client.registerAgent("test-agent", "langchain");

      expect(agentId).toBe("agent-456");
      expect(client.getAgentId()).toBe("agent-456");
      expect(fetchMock).toHaveBeenCalledWith(
        "https://api.trusera.io/api/v1/agents/register",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
            Authorization: "Bearer tsk_test123",
          }),
        })
      );
    });

    it("should throw on registration failure", async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => "Unauthorized",
      } as Response);

      const client = new TruseraClient({ apiKey: "tsk_test123" });

      await expect(client.registerAgent("test-agent", "custom")).rejects.toThrow(
        "Failed to register agent: 401 Unauthorized"
      );
    });
  });

  describe("track", () => {
    it("should queue events", () => {
      const client = new TruseraClient({
        apiKey: "tsk_test123",
        flushInterval: 999999, // Prevent auto-flush
      });

      const event = createEvent(EventType.TOOL_CALL, "test.tool");
      client.track(event);

      expect(client.getQueueSize()).toBe(1);
    });

    it("should enrich events with agent metadata", () => {
      const client = new TruseraClient({
        apiKey: "tsk_test123",
        agentId: "agent-123",
        flushInterval: 999999,
      });

      const event = createEvent(EventType.TOOL_CALL, "test.tool");
      client.track(event);

      // Queue should contain enriched event (can't inspect directly, but flush will verify)
      expect(client.getQueueSize()).toBe(1);
    });

    it("should auto-flush when batch size reached", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      } as Response);

      const client = new TruseraClient({
        apiKey: "tsk_test123",
        batchSize: 2,
        flushInterval: 999999,
      });

      client.track(createEvent(EventType.TOOL_CALL, "test1"));
      expect(fetchMock).not.toHaveBeenCalled();

      client.track(createEvent(EventType.TOOL_CALL, "test2"));

      // Wait for async flush
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(fetchMock).toHaveBeenCalledWith(
        "https://api.trusera.io/api/v1/events/batch",
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    it("should throw when tracking on closed client", async () => {
      const client = new TruseraClient({
        apiKey: "tsk_test123",
        flushInterval: 999999,
      });

      await client.close();

      expect(() => {
        client.track(createEvent(EventType.TOOL_CALL, "test"));
      }).toThrow("Cannot track events on closed client");
    });
  });

  describe("flush", () => {
    it("should send events to API", async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const client = new TruseraClient({
        apiKey: "tsk_test123",
        flushInterval: 999999,
      });

      client.track(createEvent(EventType.TOOL_CALL, "test1"));
      client.track(createEvent(EventType.LLM_INVOKE, "test2"));

      await client.flush();

      expect(fetchMock).toHaveBeenCalledOnce();
      expect(client.getQueueSize()).toBe(0);

      const callArgs = fetchMock.mock.calls[0] as unknown[];
      const body = JSON.parse(callArgs[1]!.body as string);
      expect(body.events).toHaveLength(2);
    });

    it("should respect batch size", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      } as Response);

      const client = new TruseraClient({
        apiKey: "tsk_test123",
        batchSize: 2,
        flushInterval: 999999,
      });

      // Add 5 events
      for (let i = 0; i < 5; i++) {
        client.track(createEvent(EventType.TOOL_CALL, `test${i}`));
      }

      await client.flush();

      // Should only send 2 events (batch size)
      const callArgs = fetchMock.mock.calls[0] as unknown[];
      const body = JSON.parse(callArgs[1]!.body as string);
      expect(body.events).toHaveLength(2);
      expect(client.getQueueSize()).toBe(3);
    });

    it("should handle API errors gracefully", async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => "Internal Server Error",
      } as Response);

      const client = new TruseraClient({
        apiKey: "tsk_test123",
        flushInterval: 999999,
      });

      client.track(createEvent(EventType.TOOL_CALL, "test"));
      await client.flush();

      // Events should be re-queued on failure
      expect(client.getQueueSize()).toBe(1);
    });

    it("should do nothing when queue is empty", async () => {
      const client = new TruseraClient({
        apiKey: "tsk_test123",
        flushInterval: 999999,
      });

      await client.flush();

      expect(fetchMock).not.toHaveBeenCalled();
    });
  });

  describe("close", () => {
    it("should flush remaining events", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      } as Response);

      const client = new TruseraClient({
        apiKey: "tsk_test123",
        flushInterval: 999999,
      });

      client.track(createEvent(EventType.TOOL_CALL, "test"));
      await client.close();

      expect(fetchMock).toHaveBeenCalled();
      expect(client.getQueueSize()).toBe(0);
    });

    it("should prevent further tracking", async () => {
      const client = new TruseraClient({
        apiKey: "tsk_test123",
        flushInterval: 999999,
      });

      await client.close();

      expect(() => {
        client.track(createEvent(EventType.TOOL_CALL, "test"));
      }).toThrow();
    });
  });
});
