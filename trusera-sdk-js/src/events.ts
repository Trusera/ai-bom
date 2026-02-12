/**
 * Event types tracked by the Trusera SDK.
 * These align with the core observability primitives for AI agent monitoring.
 */
export enum EventType {
  /** Tool or function call by the agent */
  TOOL_CALL = "tool_call",
  /** LLM inference invocation */
  LLM_INVOKE = "llm_invoke",
  /** Data access operation (read/write) */
  DATA_ACCESS = "data_access",
  /** Outbound HTTP API call */
  API_CALL = "api_call",
  /** File write operation */
  FILE_WRITE = "file_write",
  /** Decision point or chain step */
  DECISION = "decision",
}

/**
 * Core event structure for all Trusera tracking.
 * Events are immutable once created and queued for batch transmission.
 */
export interface Event {
  /** Unique event identifier (UUIDv4) */
  id: string;
  /** Event type discriminator */
  type: EventType;
  /** Human-readable event name (e.g., "openai.chat.completions", "github.api.repos") */
  name: string;
  /** Event-specific structured data */
  payload: Record<string, unknown>;
  /** Additional context (agent_id, session_id, tags, etc.) */
  metadata: Record<string, unknown>;
  /** ISO 8601 timestamp */
  timestamp: string;
}

/**
 * Creates a well-formed Event with automatic ID and timestamp generation.
 *
 * @param type - Event type from EventType enum
 * @param name - Descriptive event name (use dotted notation: "service.resource.action")
 * @param payload - Event-specific data (request, response, errors, etc.)
 * @param metadata - Optional metadata (merged with default agent context)
 * @returns Fully populated Event ready for tracking
 *
 * @example
 * ```typescript
 * const event = createEvent(
 *   EventType.API_CALL,
 *   "openai.chat.completions",
 *   { model: "gpt-4", tokens: 150 },
 *   { session_id: "abc-123" }
 * );
 * client.track(event);
 * ```
 */
export function createEvent(
  type: EventType,
  name: string,
  payload: Record<string, unknown> = {},
  metadata: Record<string, unknown> = {}
): Event {
  return {
    id: crypto.randomUUID(),
    type,
    name,
    payload: { ...payload },
    metadata: { ...metadata },
    timestamp: new Date().toISOString(),
  };
}

/**
 * Type guard to validate if an object is a valid Event.
 * Useful for runtime validation before transmission.
 */
export function isValidEvent(obj: unknown): obj is Event {
  if (typeof obj !== "object" || obj === null) return false;
  const e = obj as Partial<Event>;
  return (
    typeof e.id === "string" &&
    typeof e.type === "string" &&
    Object.values(EventType).includes(e.type as EventType) &&
    typeof e.name === "string" &&
    typeof e.payload === "object" &&
    e.payload !== null &&
    typeof e.metadata === "object" &&
    e.metadata !== null &&
    typeof e.timestamp === "string"
  );
}
