import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { TruseraClient } from "../src/client.js";
import { TruseraInterceptor } from "../src/interceptor.js";
import { EventType } from "../src/events.js";

// Save original fetch
const originalFetch = globalThis.fetch;
let mockFetch: ReturnType<typeof vi.fn>;
let client: TruseraClient;
let interceptor: TruseraInterceptor;

beforeEach(() => {
  // Mock fetch for API calls
  mockFetch = vi.fn();

  client = new TruseraClient({
    apiKey: "tsk_test123",
    flushInterval: 999999, // Prevent auto-flush
  });

  interceptor = new TruseraInterceptor();
});

afterEach(() => {
  // Clean up interceptor
  interceptor.uninstall();
  globalThis.fetch = originalFetch;
});

describe("TruseraInterceptor", () => {
  describe("install/uninstall", () => {
    it("should install interceptor", () => {
      interceptor.install(client);
      expect(globalThis.fetch).not.toBe(originalFetch);
    });

    it("should uninstall interceptor", () => {
      interceptor.install(client);
      interceptor.uninstall();
      expect(globalThis.fetch).toBe(originalFetch);
    });

    it("should prevent multiple interceptors", () => {
      interceptor.install(client);
      const interceptor2 = new TruseraInterceptor();

      expect(() => {
        interceptor2.install(client);
      }).toThrow("Another TruseraInterceptor is already installed");

      interceptor2.uninstall(); // Cleanup
    });

    it("should allow reinstalling same interceptor", () => {
      interceptor.install(client);
      interceptor.install(client); // Should not throw
    });
  });

  describe("fetch interception", () => {
    it("should intercept fetch calls", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
        json: async () => ({ data: "test" }),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client);

      await globalThis.fetch("https://api.example.com/test");

      expect(mockFetch).toHaveBeenCalledWith(
        "https://api.example.com/test",
        undefined
      );
      expect(client.getQueueSize()).toBeGreaterThan(0);
    });

    it("should track request and response events", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client, { debug: true });

      await globalThis.fetch("https://api.example.com/users", {
        method: "POST",
        headers: { "x-test": "value" },
      });

      // Should track: API_CALL, API_CALL.response (2 events)
      expect(client.getQueueSize()).toBeGreaterThanOrEqual(2);
    });

    it("should track errors", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client);

      await expect(
        globalThis.fetch("https://api.example.com/test")
      ).rejects.toThrow("Network error");

      // Should track: API_CALL, API_CALL.error (2 events)
      expect(client.getQueueSize()).toBeGreaterThanOrEqual(2);
    });

    it("should handle different request methods", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client);

      await globalThis.fetch("https://api.example.com/resource", { method: "PUT" });
      await globalThis.fetch("https://api.example.com/resource", { method: "DELETE" });

      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it("should handle URL object input", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client);

      const url = new URL("https://api.example.com/test");
      await globalThis.fetch(url);

      expect(mockFetch).toHaveBeenCalledWith(url, undefined);
    });

    it("should handle Request object input", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client);

      const request = new Request("https://api.example.com/test", {
        method: "POST",
      });
      await globalThis.fetch(request);

      expect(mockFetch).toHaveBeenCalledWith(request, undefined);
    });
  });

  describe("exclude patterns", () => {
    it("should exclude matching URLs", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client, {
        excludePatterns: ["^https://api\\.trusera\\.io/.*"],
      });

      // This should be excluded
      await globalThis.fetch("https://api.trusera.io/events/batch");
      expect(client.getQueueSize()).toBe(0);

      // This should be tracked
      await globalThis.fetch("https://api.example.com/test");
      expect(client.getQueueSize()).toBeGreaterThan(0);
    });

    it("should support multiple exclude patterns", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client, {
        excludePatterns: [
          "^https://api\\.trusera\\.io/.*",
          "^https://internal\\.example\\.com/.*",
        ],
      });

      await globalThis.fetch("https://api.trusera.io/test");
      await globalThis.fetch("https://internal.example.com/health");
      expect(client.getQueueSize()).toBe(0);

      await globalThis.fetch("https://external.example.com/api");
      expect(client.getQueueSize()).toBeGreaterThan(0);
    });
  });

  describe("enforcement modes", () => {
    it("should allow requests in log mode (default)", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client, {
        enforcement: "log",
      });

      const response = await globalThis.fetch("https://api.example.com/test");
      expect(response.ok).toBe(true);
    });

    it("should warn but allow in warn mode", async () => {
      const consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

      // Mock policy check to return Deny
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ decision: "Deny", reasons: ["Policy violation"] }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          statusText: "OK",
          headers: new Headers(),
        } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client, {
        enforcement: "warn",
        policyUrl: "https://policy.example.com/evaluate",
      });

      const response = await globalThis.fetch("https://api.example.com/test");

      expect(response.ok).toBe(true);
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining("[Trusera] Policy violation")
      );

      consoleWarnSpy.mockRestore();
    });

    it("should block requests in block mode", async () => {
      // Mock policy check to return Deny
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          decision: "Deny",
          reasons: ["Unauthorized API access"],
        }),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client, {
        enforcement: "block",
        policyUrl: "https://policy.example.com/evaluate",
      });

      await expect(
        globalThis.fetch("https://api.example.com/test")
      ).rejects.toThrow("[Trusera] Policy violation: Unauthorized API access");
    });

    it("should allow requests when policy check passes", async () => {
      // Mock policy check to return Allow
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ decision: "Allow" }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          statusText: "OK",
          headers: new Headers(),
        } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client, {
        enforcement: "block",
        policyUrl: "https://policy.example.com/evaluate",
      });

      const response = await globalThis.fetch("https://api.example.com/test");
      expect(response.ok).toBe(true);
    });

    it("should fail open on policy service errors", async () => {
      // Mock policy service failure
      mockFetch
        .mockRejectedValueOnce(new Error("Policy service down"))
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          statusText: "OK",
          headers: new Headers(),
        } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client, {
        enforcement: "block",
        policyUrl: "https://policy.example.com/evaluate",
      });

      // Should allow request despite policy service failure
      const response = await globalThis.fetch("https://api.example.com/test");
      expect(response.ok).toBe(true);
    });
  });

  describe("request data extraction", () => {
    it("should extract headers from Headers object", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client);

      await globalThis.fetch("https://api.example.com/test", {
        headers: new Headers({
          "x-custom": "value",
          authorization: "Bearer token",
        }),
      });

      expect(client.getQueueSize()).toBeGreaterThan(0);
    });

    it("should extract headers from object", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client);

      await globalThis.fetch("https://api.example.com/test", {
        headers: {
          "x-custom": "value",
        },
      });

      expect(client.getQueueSize()).toBeGreaterThan(0);
    });

    it("should extract string body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers(),
      } as Response);

      globalThis.fetch = mockFetch as unknown as typeof fetch;
      interceptor.install(client);

      await globalThis.fetch("https://api.example.com/test", {
        method: "POST",
        body: JSON.stringify({ key: "value" }),
      });

      expect(client.getQueueSize()).toBeGreaterThan(0);
    });
  });
});
