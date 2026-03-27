/**
 * Event reporting for the Trusera Sidecar.
 *
 * Batches events and sends them to the Trusera platform.
 * Unlike the SDK's TruseraClient (which uses a flush timer for long-running
 * processes), this reporter flushes synchronously at the end of node execution
 * since n8n nodes are short-lived.
 */

import { randomUUID } from 'crypto';
import type { SidecarEvent, SidecarEventType, EvaluationResult, PolicyGateResult } from './types';
import { SidecarEventType as EventType } from './types';

const MAX_QUEUE_SIZE = 10_000;
const BATCH_SIZE = 100;
const MAX_EVENT_PAYLOAD_SIZE = 10_000; // 10 KB per event payload

/** Module-level cache for agent registrations (survives across workflow executions). */
const agentRegistrationCache = new Map<string, string>();

export class SidecarReporter {
  private platformUrl: string;
  private apiKey: string;
  private agentName: string;
  private eventQueue: SidecarEvent[] = [];

  constructor(platformUrl: string, apiKey: string, agentName: string) {
    this.platformUrl = platformUrl.replace(/\/+$/, '');
    this.apiKey = apiKey;
    this.agentName = agentName;
  }

  /**
   * Register the agent with the platform. Cached per agentName+platformUrl.
   * Returns the agent_id, or 'unregistered' if registration fails.
   */
  async ensureRegistered(): Promise<string> {
    const cacheKey = `${this.agentName}::${this.platformUrl}`;
    const cached = agentRegistrationCache.get(cacheKey);
    if (cached) return cached;

    try {
      const res = await fetch(`${this.platformUrl}/api/v1/agents/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          name: this.agentName,
          framework: 'n8n',
          metadata: {
            sdk_version: '0.6.0',
            runtime: 'n8n-node',
            node_type: 'TruseraSidecar',
          },
        }),
      });

      if (res.ok) {
        const data = (await res.json()) as { agent_id?: string };
        const agentId = data.agent_id ?? 'unregistered';
        agentRegistrationCache.set(cacheKey, agentId);
        return agentId;
      }
    } catch {
      // Registration failure is non-fatal
    }

    return 'unregistered';
  }

  /** Queue an event for batch reporting. */
  track(event: SidecarEvent): void {
    if (this.eventQueue.length >= MAX_QUEUE_SIZE) return;
    this.eventQueue.push(event);
  }

  /** Flush all queued events to the platform in batches. */
  async flush(): Promise<void> {
    if (this.eventQueue.length === 0) return;

    const agentId = await this.ensureRegistered();
    const events = this.eventQueue.splice(0);

    for (let i = 0; i < events.length; i += BATCH_SIZE) {
      const batch = events.slice(i, i + BATCH_SIZE);
      try {
        await fetch(`${this.platformUrl}/api/v1/events/batch`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.apiKey}`,
          },
          body: JSON.stringify({
            events: batch.map((e) => ({
              id: e.id,
              type: e.type,
              name: `n8n.sidecar.${e.type}`,
              payload: e.payload,
              metadata: {
                agent_id: agentId,
                agent_name: e.agentName,
                sdk_version: '0.6.0',
                runtime: 'n8n-node',
              },
              timestamp: e.timestamp,
            })),
          }),
        });
      } catch {
        // Event reporting is fire-and-forget
      }
    }
  }

  /** Create a structured event from an evaluation result. */
  createEvaluationEvent(
    result: EvaluationResult,
    inputData: Record<string, unknown>,
    nodeName: string,
    workflowId?: string,
  ): SidecarEvent {
    const hasViolations = result.violations.length > 0;
    const payload: Record<string, unknown> = {
      agent_name: this.agentName,
      node_name: nodeName,
      enforcement_mode: result.enforcement,
      decision: hasViolations ? 'deny' : 'allow',
      duration_ms: result.durationMs,
      violations_count: result.violations.length,
      checks: Object.fromEntries(
        result.checks.map((c) => [
          c.name,
          { passed: c.passed, ...(c.findings?.length ? { findings: c.findings } : {}) },
        ]),
      ),
    };

    if (workflowId) payload.workflow_id = workflowId;

    // Truncate payload to max size
    const payloadStr = JSON.stringify(payload);
    if (payloadStr.length > MAX_EVENT_PAYLOAD_SIZE) {
      payload.checks = { truncated: true };
    }

    return {
      id: randomUUID(),
      type: result.violations.length > 0
        ? ('policy_evaluation' as SidecarEventType)
        : ('policy_evaluation' as SidecarEventType),
      agentName: this.agentName,
      workflowId,
      nodeName,
      payload,
      result: hasViolations ? 'deny' : 'allow',
      timestamp: result.timestamp,
    };
  }

  /** Create a structured event from a policy gate (tool-call) result. */
  createToolCallEvent(
    result: PolicyGateResult,
    nodeName: string,
    workflowId?: string,
  ): SidecarEvent {
    const hasViolations = result.violations.length > 0;

    let eventType: SidecarEventType;
    if (!hasViolations) {
      eventType = EventType.TOOL_CALL_APPROVED;
    } else if (result.enforcement === 'block') {
      eventType = EventType.TOOL_CALL_DENIED;
    } else {
      eventType = EventType.TOOL_CALL_WARNED;
    }

    const payload: Record<string, unknown> = {
      agent_name: this.agentName,
      node_name: nodeName,
      tool_name: result.proposal.toolName,
      decision: hasViolations ? 'deny' : 'allow',
      enforcement_mode: result.enforcement,
      duration_ms: result.durationMs,
      violations_count: result.violations.length,
      violations: result.violations.map((v) => ({ policy: v.policyName, reason: v.reason, severity: v.severity })),
      checks: Object.fromEntries(
        result.checks.map((c) => [c.name, { passed: c.passed }]),
      ),
    };

    if (result.brainAnalysis) {
      payload.brain_analysis = {
        decision: result.brainAnalysis.decision,
        confidence: result.brainAnalysis.confidence,
        reasoning: result.brainAnalysis.reasoning.slice(0, 500),
      };
    }

    if (workflowId) payload.workflow_id = workflowId;

    return {
      id: randomUUID(),
      type: eventType,
      agentName: this.agentName,
      workflowId,
      nodeName,
      payload,
      result: hasViolations ? 'deny' : 'allow',
      timestamp: result.timestamp,
    };
  }
}
