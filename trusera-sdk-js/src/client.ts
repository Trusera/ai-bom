import type { Event } from "./events.js";

const SDK_VERSION = "1.0.0";

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
  /** Auto-register with fleet discovery on startup (default: false).
   *  Overridden by TRUSERA_AUTO_REGISTER env var. */
  autoRegister?: boolean;
  /** Agent name for fleet registration (defaults to os.hostname()) */
  agentName?: string;
  /** Agent type for fleet registration (e.g. "langchain") */
  agentType?: string;
  /** Deployment environment for fleet registration */
  environment?: string;
  /** Heartbeat interval in ms (default: 60000).
   *  Overridden by TRUSERA_HEARTBEAT_INTERVAL env var. */
  heartbeatInterval?: number;
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

  // Fleet auto-registration
  private readonly autoRegister: boolean;
  private readonly agentName: string;
  private readonly agentType: string;
  private readonly environment: string;
  private readonly heartbeatInterval: number;
  private fleetAgentId: string | undefined;
  private heartbeatTimer: NodeJS.Timeout | undefined;

  constructor(options: TruseraClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = options.baseUrl ?? "https://api.trusera.io";
    this.agentId = options.agentId;
    this.batchSize = options.batchSize ?? 100;
    this.flushInterval = options.flushInterval ?? 5000;
    this.debug = options.debug ?? false;

    // Fleet config with env var overrides
    const envAuto = (typeof process !== "undefined" ? process.env?.TRUSERA_AUTO_REGISTER : undefined) ?? "";
    if (envAuto.toLowerCase() === "true" || envAuto === "1") {
      this.autoRegister = true;
    } else if (envAuto.toLowerCase() === "false" || envAuto === "0") {
      this.autoRegister = false;
    } else {
      this.autoRegister = options.autoRegister ?? false;
    }

    const hostname = typeof process !== "undefined" && process.env?.HOSTNAME
      ? process.env.HOSTNAME
      : typeof globalThis !== "undefined" && "navigator" in globalThis
        ? "browser"
        : "unknown";
    this.agentName = options.agentName ?? (typeof process !== "undefined" ? process.env?.TRUSERA_AGENT_NAME : undefined) ?? hostname;
    this.agentType = options.agentType ?? (typeof process !== "undefined" ? process.env?.TRUSERA_AGENT_TYPE : undefined) ?? "";
    this.environment = options.environment ?? (typeof process !== "undefined" ? process.env?.TRUSERA_ENVIRONMENT : undefined) ?? "";
    const envHb = typeof process !== "undefined" ? process.env?.TRUSERA_HEARTBEAT_INTERVAL : undefined;
    this.heartbeatInterval = envHb ? parseInt(envHb, 10) * 1000 : (options.heartbeatInterval ?? 60000);

    if (!this.apiKey.startsWith("tsk_")) {
      throw new Error("Invalid API key format. Must start with 'tsk_'");
    }

    // Start auto-flush timer
    this.startFlushTimer();

    // Fleet auto-registration
    if (this.autoRegister) {
      void this.registerWithFleet();
    }

    this.log("TruseraClient initialized", { baseUrl: this.baseUrl, batchSize: this.batchSize, autoRegister: this.autoRegister });
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
    this.stopHeartbeat();
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

  // -- Fleet auto-registration --

  private getProcessInfo(): Record<string, unknown> {
    if (typeof process === "undefined") return {};
    return {
      pid: process.pid,
      argv: process.argv?.slice(0, 10),
      node_version: process.version,
      platform: process.platform,
      arch: process.arch,
    };
  }

  private getNetworkInfo(): Record<string, unknown> {
    const info: Record<string, unknown> = {};
    if (typeof process !== "undefined") {
      try {
        const os = require("os");
        info.hostname = os.hostname?.();
      } catch {
        info.hostname = process.env?.HOSTNAME ?? "unknown";
      }
    }
    return info;
  }

  private async registerWithFleet(): Promise<void> {
    const payload: Record<string, unknown> = {
      name: this.agentName,
      discovery_method: "sdk",
      sdk_version: SDK_VERSION,
      hostname: this.agentName,
      process_info: this.getProcessInfo(),
      network_info: this.getNetworkInfo(),
    };
    if (this.agentType) payload.framework = this.agentType;
    if (this.environment) payload.environment = this.environment;

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/fleet/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        this.log("Fleet auto-register failed", { status: response.status });
        return;
      }

      const data = await response.json() as { data?: { id?: string }; id?: string };
      const agentData = data.data ?? data;
      const fleetId = agentData.id;
      if (fleetId) {
        this.fleetAgentId = String(fleetId);
        this.startHeartbeat();
        this.log("Fleet auto-register succeeded", { fleetAgentId: this.fleetAgentId });
      }
    } catch (err) {
      this.log("Fleet auto-register error (continuing without)", { error: String(err) });
    }
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      void this.sendHeartbeat();
    }, this.heartbeatInterval);

    if (this.heartbeatTimer.unref) {
      this.heartbeatTimer.unref();
    }
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
  }

  private async sendHeartbeat(): Promise<void> {
    if (!this.fleetAgentId) return;
    try {
      const payload = {
        process_info: this.getProcessInfo(),
        network_info: this.getNetworkInfo(),
      };
      const response = await fetch(`${this.baseUrl}/api/v1/fleet/${this.fleetAgentId}/heartbeat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        this.log("Fleet heartbeat failed", { status: response.status });
      }
    } catch (err) {
      this.log("Fleet heartbeat error", { error: String(err) });
    }
  }

  // -- Timers --

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
