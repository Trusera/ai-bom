import { describe, it, expect } from "vitest";
import { EventType, createEvent, isValidEvent } from "../src/events.js";

describe("EventType", () => {
  it("should have all expected event types", () => {
    expect(EventType.TOOL_CALL).toBe("tool_call");
    expect(EventType.LLM_INVOKE).toBe("llm_invoke");
    expect(EventType.DATA_ACCESS).toBe("data_access");
    expect(EventType.API_CALL).toBe("api_call");
    expect(EventType.FILE_WRITE).toBe("file_write");
    expect(EventType.DECISION).toBe("decision");
  });

  it("should have 6 event types", () => {
    expect(Object.keys(EventType)).toHaveLength(6);
  });
});

describe("createEvent", () => {
  it("should create event with minimal params", () => {
    const event = createEvent(EventType.TOOL_CALL, "test.tool");

    expect(event.id).toBeTruthy();
    expect(event.type).toBe(EventType.TOOL_CALL);
    expect(event.name).toBe("test.tool");
    expect(event.payload).toEqual({});
    expect(event.metadata).toEqual({});
    expect(event.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("should create event with payload", () => {
    const payload = { input: "test", tokens: 100 };
    const event = createEvent(EventType.LLM_INVOKE, "openai.chat", payload);

    expect(event.payload).toEqual(payload);
    expect(event.payload).not.toBe(payload); // Should be a copy
  });

  it("should create event with metadata", () => {
    const metadata = { session_id: "abc-123", user: "test" };
    const event = createEvent(EventType.API_CALL, "github.api", {}, metadata);

    expect(event.metadata).toEqual(metadata);
    expect(event.metadata).not.toBe(metadata); // Should be a copy
  });

  it("should generate unique IDs", () => {
    const event1 = createEvent(EventType.TOOL_CALL, "test");
    const event2 = createEvent(EventType.TOOL_CALL, "test");

    expect(event1.id).not.toBe(event2.id);
  });

  it("should generate timestamps in ISO format", () => {
    const event = createEvent(EventType.DECISION, "test");
    const timestamp = new Date(event.timestamp);

    expect(timestamp.toISOString()).toBe(event.timestamp);
  });
});

describe("isValidEvent", () => {
  it("should validate correct event", () => {
    const event = createEvent(EventType.TOOL_CALL, "test");
    expect(isValidEvent(event)).toBe(true);
  });

  it("should reject non-object", () => {
    expect(isValidEvent(null)).toBe(false);
    expect(isValidEvent(undefined)).toBe(false);
    expect(isValidEvent("string")).toBe(false);
    expect(isValidEvent(123)).toBe(false);
  });

  it("should reject missing required fields", () => {
    expect(isValidEvent({})).toBe(false);
    expect(isValidEvent({ id: "test" })).toBe(false);
    expect(isValidEvent({ id: "test", type: EventType.TOOL_CALL })).toBe(false);
  });

  it("should reject invalid event type", () => {
    const event = createEvent(EventType.TOOL_CALL, "test");
    expect(isValidEvent({ ...event, type: "invalid_type" })).toBe(false);
  });

  it("should reject null payload or metadata", () => {
    const event = createEvent(EventType.TOOL_CALL, "test");
    expect(isValidEvent({ ...event, payload: null })).toBe(false);
    expect(isValidEvent({ ...event, metadata: null })).toBe(false);
  });

  it("should reject invalid field types", () => {
    const event = createEvent(EventType.TOOL_CALL, "test");
    expect(isValidEvent({ ...event, id: 123 })).toBe(false);
    expect(isValidEvent({ ...event, name: null })).toBe(false);
    expect(isValidEvent({ ...event, timestamp: null })).toBe(false);
  });
});
