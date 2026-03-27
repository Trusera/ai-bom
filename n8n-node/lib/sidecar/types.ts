/**
 * Shared types for the Trusera Sidecar runtime enforcement.
 */

/** Enforcement mode — what happens when a policy violation is detected. */
export type EnforcementMode = 'log' | 'warn' | 'block';

/** Where to load Cedar policies from. */
export type PolicySource = 'platform' | 'inline';

/** Severity levels for policy violations. */
export type ViolationSeverity = 'critical' | 'high' | 'medium' | 'low';

/** A single policy violation. */
export interface Violation {
  policyName: string;
  reason: string;
  severity: ViolationSeverity;
}

/** Result of an individual check (PII, injection, Cedar, etc.). */
export interface CheckResult {
  name: string;
  passed: boolean;
  details: string;
  findings?: string[];
}

/** Aggregate evaluation result from the sidecar pipeline. */
export interface EvaluationResult {
  allowed: boolean;
  enforcement: EnforcementMode;
  violations: Violation[];
  checks: CheckResult[];
  timestamp: string;
  durationMs: number;
}

/** Event types reported to the Trusera platform. */
export enum SidecarEventType {
  POLICY_EVALUATION = 'policy_evaluation',
  PII_DETECTED = 'pii_detected',
  CONTENT_FILTERED = 'content_filtered',
  PROMPT_INJECTION = 'prompt_injection',
  WORKFLOW_BLOCKED = 'workflow_blocked',
  TOOL_VALIDATION = 'tool_validation',
  TOOL_CALL_APPROVED = 'tool_call_approved',
  TOOL_CALL_DENIED = 'tool_call_denied',
  TOOL_CALL_WARNED = 'tool_call_warned',
}

/** A single event sent to the platform via /api/v1/events/batch. */
export interface SidecarEvent {
  id: string;
  type: SidecarEventType;
  agentName: string;
  workflowId?: string;
  nodeName?: string;
  payload: Record<string, unknown>;
  result: 'allow' | 'deny' | 'warn';
  timestamp: string;
}

/** Cedar policy fetched from the platform. */
export interface CedarPolicy {
  id: string;
  name: string;
  cedar_dsl: string;
  description: string;
  enabled: boolean;
  enforcement_mode: EnforcementMode;
}

/** Configuration for the SidecarEvaluator. */
export interface EvaluatorConfig {
  platformUrl: string;
  apiKey: string;
  enforcementMode: EnforcementMode;
  policySource: PolicySource;
  agentName: string;
  enablePiiDetection: boolean;
  enableContentFilter: boolean;
  enablePromptInjection: boolean;
  inlineCedarDsl?: string;
  policyCacheTtlMs: number;
}

// ── Policy Gate types (v2 — tool-call interception) ──

/** A proposed tool call submitted to the policy gate. */
export interface ToolCallProposal {
  toolName: string;
  toolArgs: Record<string, unknown>;
  reasoning: string;
  containsPii: boolean;
  dataSummary: string;
}

/** Result of a policy gate evaluation. */
export interface PolicyGateResult extends EvaluationResult {
  proposal: ToolCallProposal;
  brainAnalysis?: BrainAnalysis;
  policySummaries: string[];
}

/** Result from the AI-powered brain mode evaluation. */
export interface BrainAnalysis {
  decision: 'allow' | 'deny' | 'warn';
  reasoning: string;
  confidence: number;
  flaggedConcerns: string[];
  durationMs: number;
}

/** Configuration for brain mode. */
export interface BrainModeConfig {
  enabled: boolean;
  model?: string;
  maxTokens?: number;
  temperature?: number;
}

/** Extended evaluator config for the policy gate. */
export interface PolicyGateConfig extends EvaluatorConfig {
  brainMode: BrainModeConfig;
  brainApiKey?: string;
  brainBaseUrl?: string;
}
