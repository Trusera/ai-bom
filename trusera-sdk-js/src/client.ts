import type { Event } from "./events.js";

/**
 * Configuration options for TruseraClient.
 */
export interface TruseraClientOptions {
  /** API key for authenticating with Trusera backend (tsk_xxx) */
  apiKey: string;
  /** Base URL for Trusera API (defaults to production) */
  baseUrl?: string;
  /** Agent identifier (auto-registered if not provided) */
  agentId?: string;
  /** Interval in ms to auto-flush events (default: 5000) */
  flushInterval?: number;
  /** Max events per batch (default: 100) */
  batchSize?: number;
  /** Enable debug logging to console */
  debug?: boolean;
}

/**
 * Response from agent registration endpoint.
 */
interface RegisterAgentResponse {
  agent_id: string;
  name: string;
  created_at: string;
}

/**
 * Core client for tracking AI agent events and sending them to Trusera.
 * Handles batching, automatic flushing, and agent registration.
 *
 * @example
 * ```typescript
 * const client = new TruseraClient({
 *   apiKey: "tsk_your_key_here",
 *   agentId: "my-agent-123"
 * });
 *
 * client.track(createEvent(EventType.TOOL_CALL, "github.search", { query: "AI" }));
 * await client.close(); // Flush remaining events and cleanup
 * ```
 */
export class TruseraClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly batchSize: number;
  private readonly flushInterval: number;
  private readonly debug: boolean;

  private agentId: string | undefined;
  private eventQueue: Event[] = [];
  private flushTimer: NodeJS.Timeout | undefined;
  private isClosed = false;

  constructor(options: TruseraClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = options.baseUrl ?? "https://api.trusera.io";
    this.agentId = options.agentId;
    this.batchSize = options.batchSize ?? 100;
    this.flushInterval = options.flushInterval ?? 5000;
    this.debug = options.debug ?? false;

    if (!this.apiKey.startsWith("tsk_")) {
      throw new Error("Invalid API key format. Must start with 'tsk_'");
    }

    // Start auto-flush timer
    this.startFlushTimer();
    this.log("TruseraClient initialized", { baseUrl: this.baseUrl, batchSize: this.batchSize });
  }

  /**
   * Registers a new agent with Trusera backend.
   * Returns the assigned agent_id which should be stored for future use.
   *
   * @param name - Human-readable agent name
   * @param framework - Framework identifier (e.g., "langchain", "autogen", "custom")
   * @returns Agent ID string
   */
  async registerAgent(name: string, framework: string): Promise<string> {
    this.log("Registering agent", { name, framework });

    const response = await fetch(`${this.baseUrl}/api/v1/agents/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        name,
        framework,
        metadata: {
          sdk_version: "0.1.0",
          runtime: "node",
          node_version: process.version,
        },
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to register agent: ${response.status} ${error}`);
    }

    const data = (await response.json()) as RegisterAgentResponse;
    this.agentId = data.agent_id;
    this.log("Agent registered", { agentId: this.agentId });
    return this.agentId;
  }

  /**
   * Queues an event for transmission.
   * Events are batched and sent automatically based on flushInterval and batchSize.
   *
   * @param event - Event to track
   */
  track(event: Event): void {
    if (this.isClosed) {
      throw new Error("Cannot track events on closed client");
    }

    // Enrich metadata with agent context
    const enrichedEvent: Event = {
      ...event,
      metadata: {
        ...event.metadata,
        agent_id: this.agentId,
        sdk_version: "0.1.0",
      },
    };

    this.eventQueue.push(enrichedEvent);
    this.log("Event tracked", { type: event.type, name: event.name, queueSize: this.eventQueue.length });

    // Auto-flush if batch size reached
    if (this.eventQueue.length >= this.batchSize) {
      void this.flush();
    }
  }

  /**
   * Immediately sends all queued events to Trusera backend.
   * Called automatically by flush timer or when batch size is reached.
   *
   * @returns Promise that resolves when events are sent
   */
  async flush(): Promise<void> {
    if (this.eventQueue.length === 0) {
      return;
    }

    const batch = this.eventQueue.splice(0, this.batchSize);
    this.log("Flushing events", { count: batch.length });

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/events/batch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({ events: batch }),
      });

      if (!response.ok) {
        const error = await response.text();
        console.error(`[Trusera] Failed to send events: ${response.status} ${error}`);
        // Re-queue failed events for retry
        this.eventQueue.unshift(...batch);
      } else {
        this.log("Events flushed successfully", { count: batch.length });
      }
    } catch (error) {
      console.error("[Trusera] Network error sending events:", error);
      // Re-queue failed events
      this.eventQueue.unshift(...batch);
    }
  }

  /**
   * Gracefully shuts down the client.
   * Flushes all remaining events and stops the auto-flush timer.
   *
   * @returns Promise that resolves when shutdown is complete
   */
  async close(): Promise<void> {
    this.log("Closing client");
    this.isClosed = true;
    this.stopFlushTimer();
    await this.flush();
    this.log("Client closed");
  }

  /**
   * Returns current queue size (useful for monitoring/debugging).
   */
  getQueueSize(): number {
    return this.eventQueue.length;
  }

  /**
   * Returns the current agent ID (if registered).
   */
  getAgentId(): string | undefined {
    return this.agentId;
  }

  private startFlushTimer(): void {
    this.flushTimer = setInterval(() => {
      void this.flush();
    }, this.flushInterval);

    // Don't keep process alive for flush timer
    if (this.flushTimer.unref) {
      this.flushTimer.unref();
    }
  }

  private stopFlushTimer(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = undefined;
    }
  }

  private log(message: string, data?: Record<string, unknown>): void {
    if (this.debug) {
      console.log(`[Trusera] ${message}`, data ?? "");
    }
  }
}
