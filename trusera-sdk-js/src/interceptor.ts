import type { TruseraClient } from "./client.js";
import { EventType, createEvent } from "./events.js";

/**
 * Enforcement modes for policy violations.
 */
export type EnforcementMode = "block" | "warn" | "log";

/**
 * Configuration for the HTTP interceptor.
 */
export interface InterceptorOptions {
  /** How to handle policy violations (default: "log") */
  enforcement?: EnforcementMode;
  /** Cedar policy service URL for runtime policy checks */
  policyUrl?: string;
  /** URL patterns to exclude from interception (regex strings) */
  excludePatterns?: string[];
  /** Enable debug logging */
  debug?: boolean;
}

/**
 * Policy evaluation request sent to Cedar policy service.
 */
interface PolicyEvaluationRequest {
  principal: string;
  action: string;
  resource: string;
  context: Record<string, unknown>;
}

/**
 * Policy evaluation response from Cedar service.
 */
interface PolicyEvaluationResponse {
  decision: "Allow" | "Deny";
  reasons?: string[];
}

/**
 * Global interceptor singleton state.
 * Only one interceptor can be active at a time.
 */
let activeInterceptor: TruseraInterceptor | null = null;
let originalFetch: typeof globalThis.fetch | null = null;

/**
 * HTTP interceptor for AI agent outbound traffic.
 * Monkey-patches globalThis.fetch to intercept all HTTP calls,
 * evaluate them against Cedar policies, and track events.
 *
 * This is the core differentiator of the Trusera SDK - transparent
 * runtime monitoring without code changes.
 *
 * @example
 * ```typescript
 * const client = new TruseraClient({ apiKey: "tsk_xxx" });
 * const interceptor = new TruseraInterceptor();
 *
 * interceptor.install(client, {
 *   enforcement: "block",
 *   policyUrl: "https://policy.trusera.io/evaluate",
 *   excludePatterns: ["^https://api\\.trusera\\.io/.*"]
 * });
 *
 * // All fetch calls are now intercepted
 * await fetch("https://api.github.com/repos/test"); // Tracked + policy-checked
 *
 * interceptor.uninstall(); // Restore original fetch
 * ```
 */
export class TruseraInterceptor {
  private client: TruseraClient | null = null;
  private options: Required<InterceptorOptions> = {
    enforcement: "log",
    policyUrl: "",
    excludePatterns: [],
    debug: false,
  };
  private excludeRegexes: RegExp[] = [];
  private isInstalled = false;

  /**
   * Installs the HTTP interceptor by patching globalThis.fetch.
   * Only one interceptor can be active at a time.
   *
   * @param client - TruseraClient instance for event tracking
   * @param options - Interceptor configuration
   * @throws Error if another interceptor is already installed
   */
  install(client: TruseraClient, options: InterceptorOptions = {}): void {
    if (activeInterceptor !== null && activeInterceptor !== this) {
      throw new Error("Another TruseraInterceptor is already installed. Call uninstall() first.");
    }

    if (this.isInstalled) {
      this.log("Interceptor already installed");
      return;
    }

    this.client = client;
    this.options = {
      enforcement: options.enforcement ?? "log",
      policyUrl: options.policyUrl ?? "",
      excludePatterns: options.excludePatterns ?? [],
      debug: options.debug ?? false,
    };

    // Compile exclude patterns to regexes
    this.excludeRegexes = this.options.excludePatterns.map((pattern) => new RegExp(pattern));

    // Save original fetch and install interceptor
    if (originalFetch === null) {
      originalFetch = globalThis.fetch;
    }

    globalThis.fetch = this.createInterceptedFetch();
    activeInterceptor = this;
    this.isInstalled = true;

    this.log("Interceptor installed", {
      enforcement: this.options.enforcement,
      policyUrl: this.options.policyUrl,
      excludePatterns: this.options.excludePatterns.length,
    });
  }

  /**
   * Uninstalls the interceptor and restores original fetch.
   */
  uninstall(): void {
    if (!this.isInstalled) {
      return;
    }

    if (originalFetch !== null) {
      globalThis.fetch = originalFetch;
    }

    activeInterceptor = null;
    this.isInstalled = false;
    this.client = null;

    this.log("Interceptor uninstalled");
  }

  /**
   * Creates the intercepted fetch function.
   * This is the core of the interception logic.
   */
  private createInterceptedFetch(): typeof globalThis.fetch {
    const self = this;

    return async function interceptedFetch(
      input: RequestInfo | URL,
      init?: RequestInit
    ): Promise<Response> {
      // Ensure we have original fetch to fall back to
      if (originalFetch === null) {
        throw new Error("Original fetch not available");
      }

      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const method = init?.method ?? "GET";

      // Check if URL should be excluded
      if (self.shouldExclude(url)) {
        self.log("Skipping excluded URL", { url });
        return originalFetch(input, init);
      }

      self.log("Intercepting request", { method, url });

      // Extract request details
      const requestData = await self.extractRequestData(input, init);

      // Create tracking event
      const event = createEvent(
        EventType.API_CALL,
        self.generateEventName(url, method),
        {
          method,
          url,
          headers: requestData.headers,
          body: requestData.body,
        },
        {
          interception_mode: self.options.enforcement,
        }
      );

      // Evaluate policy if configured
      if (self.options.policyUrl) {
        const policyDecision = await self.evaluatePolicy(url, method, requestData);

        if (policyDecision.decision === "Deny") {
          self.log("Policy violation detected", { url, reasons: policyDecision.reasons });

          // Track violation event
          const violationEvent = createEvent(
            EventType.API_CALL,
            `${self.generateEventName(url, method)}.policy_violation`,
            {
              ...event.payload,
              policy_decision: "Deny",
              policy_reasons: policyDecision.reasons,
            }
          );

          self.client?.track(violationEvent);

          // Handle based on enforcement mode
          if (self.options.enforcement === "block") {
            throw new Error(
              `[Trusera] Policy violation: ${policyDecision.reasons?.join(", ") ?? "Request denied"}`
            );
          } else if (self.options.enforcement === "warn") {
            console.warn(
              `[Trusera] Policy violation (allowed): ${policyDecision.reasons?.join(", ") ?? "Request denied"}`
            );
          }
        } else {
          self.log("Policy check passed", { url });
        }
      }

      // Track the API call event
      self.client?.track(event);

      // Execute the actual request
      const startTime = Date.now();
      let response: Response;
      let error: Error | undefined;

      try {
        response = await originalFetch(input, init);
      } catch (err) {
        error = err as Error;
        self.log("Request failed", { url, error: error.message });

        // Track error event
        const errorEvent = createEvent(
          EventType.API_CALL,
          `${self.generateEventName(url, method)}.error`,
          {
            ...event.payload,
            error: error.message,
            duration_ms: Date.now() - startTime,
          }
        );
        self.client?.track(errorEvent);

        throw error;
      }

      // Track response
      const responseEvent = createEvent(
        EventType.API_CALL,
        `${self.generateEventName(url, method)}.response`,
        {
          ...event.payload,
          status: response.status,
          status_text: response.statusText,
          duration_ms: Date.now() - startTime,
          response_headers: Object.fromEntries(response.headers.entries()),
        }
      );
      self.client?.track(responseEvent);

      return response;
    };
  }

  /**
   * Checks if a URL should be excluded from interception.
   */
  private shouldExclude(url: string): boolean {
    return this.excludeRegexes.some((regex) => regex.test(url));
  }

  /**
   * Extracts request data for policy evaluation and tracking.
   */
  private async extractRequestData(
    input: RequestInfo | URL,
    init?: RequestInit
  ): Promise<{ headers: Record<string, string>; body: string | null }> {
    const headers: Record<string, string> = {};

    // Extract headers
    if (init?.headers) {
      if (init.headers instanceof Headers) {
        init.headers.forEach((value, key) => {
          headers[key] = value;
        });
      } else if (Array.isArray(init.headers)) {
        for (const [key, value] of init.headers) {
          headers[key] = value;
        }
      } else {
        Object.assign(headers, init.headers);
      }
    }

    // Extract body (if present and serializable)
    let body: string | null = null;
    if (init?.body) {
      if (typeof init.body === "string") {
        body = init.body;
      } else if (init.body instanceof URLSearchParams) {
        body = init.body.toString();
      } else if (init.body instanceof FormData) {
        body = "[FormData]";
      } else {
        body = "[Binary data]";
      }
    }

    return { headers, body };
  }

  /**
   * Evaluates request against Cedar policies.
   */
  private async evaluatePolicy(
    url: string,
    method: string,
    requestData: { headers: Record<string, string>; body: string | null }
  ): Promise<PolicyEvaluationResponse> {
    if (!this.options.policyUrl || !originalFetch) {
      return { decision: "Allow" };
    }

    try {
      const evaluationRequest: PolicyEvaluationRequest = {
        principal: this.client?.getAgentId() ?? "unknown-agent",
        action: `http.${method.toLowerCase()}`,
        resource: url,
        context: {
          headers: requestData.headers,
          body_present: requestData.body !== null,
          timestamp: new Date().toISOString(),
        },
      };

      const response = await originalFetch(this.options.policyUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(evaluationRequest),
      });

      if (!response.ok) {
        console.error(`[Trusera] Policy evaluation failed: ${response.status}`);
        return { decision: "Allow" }; // Fail open
      }

      return (await response.json()) as PolicyEvaluationResponse;
    } catch (error) {
      console.error("[Trusera] Policy evaluation error:", error);
      return { decision: "Allow" }; // Fail open on error
    }
  }

  /**
   * Generates a structured event name from URL and method.
   */
  private generateEventName(url: string, method: string): string {
    try {
      const urlObj = new URL(url);
      const hostname = urlObj.hostname.replace(/\./g, "_");
      const path = urlObj.pathname.split("/").filter(Boolean).join("_") || "root";
      return `http.${method.toLowerCase()}.${hostname}.${path}`;
    } catch {
      return `http.${method.toLowerCase()}.invalid_url`;
    }
  }

  private log(message: string, data?: Record<string, unknown>): void {
    if (this.options.debug) {
      console.log(`[Trusera Interceptor] ${message}`, data ?? "");
    }
  }
}
