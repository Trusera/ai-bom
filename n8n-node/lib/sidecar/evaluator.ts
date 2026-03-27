/**
 * Core evaluation pipeline for the Trusera Sidecar.
 *
 * Combines Cedar policy evaluation, PII detection, and content filtering
 * into a single evaluation pipeline with fail-open design.
 */

import type {
  EvaluatorConfig,
  EvaluationResult,
  CheckResult,
  Violation,
  CedarPolicy,
} from './types';
import { detectPii, redactPii } from './pii';
import { detectPromptInjection, detectDangerousContent, runContentFilter } from './contentFilter';

/** Max context size sent to platform (50 KB). */
const MAX_CONTEXT_SIZE = 50_000;

/** Module-level policy cache. */
const policyCache = new Map<string, { policies: CedarPolicy[]; fetchedAt: number }>();

export class SidecarEvaluator {
  private config: EvaluatorConfig;

  constructor(config: EvaluatorConfig) {
    this.config = config;
  }

  /** Main evaluation entry point. */
  async evaluate(data: Record<string, unknown>): Promise<EvaluationResult> {
    const startTime = Date.now();
    const checks: CheckResult[] = [];
    const violations: Violation[] = [];

    // Extract all text content from the input data
    const textContent = this.extractTextContent(data);

    // Run built-in checks
    if (this.config.enablePiiDetection) {
      const piiCheck = this.checkPii(textContent);
      checks.push(piiCheck);
      if (!piiCheck.passed) {
        violations.push({
          policyName: 'pii_detection',
          reason: `PII detected: ${piiCheck.findings?.join(', ') ?? 'unknown types'}`,
          severity: 'high',
        });
      }
    }

    if (this.config.enablePromptInjection) {
      const injectionCheck = this.checkPromptInjection(textContent);
      checks.push(injectionCheck);
      if (!injectionCheck.passed) {
        violations.push({
          policyName: 'prompt_injection',
          reason: `Prompt injection detected: ${injectionCheck.findings?.join(', ') ?? 'unknown pattern'}`,
          severity: 'critical',
        });
      }
    }

    if (this.config.enableContentFilter) {
      const contentCheck = this.checkContentFilter(textContent);
      checks.push(contentCheck);
      if (!contentCheck.passed) {
        violations.push({
          policyName: 'content_filter',
          reason: `Dangerous content detected: ${contentCheck.findings?.join(', ') ?? 'unknown pattern'}`,
          severity: 'high',
        });
      }
    }

    // Cedar policy evaluation
    const cedarCheck = await this.evaluateCedarPolicies(data, checks);
    checks.push(cedarCheck);
    if (!cedarCheck.passed) {
      violations.push({
        policyName: 'cedar_policy',
        reason: cedarCheck.details,
        severity: 'high',
      });
    }

    const durationMs = Date.now() - startTime;
    const allowed =
      violations.length === 0 || this.config.enforcementMode !== 'block';

    return {
      allowed: violations.length === 0 ? true : allowed,
      enforcement: this.config.enforcementMode,
      violations,
      checks,
      timestamp: new Date().toISOString(),
      durationMs,
    };
  }

  /** PII detection check. */
  private checkPii(text: string): CheckResult {
    const matches = detectPii(text);
    if (matches.length === 0) {
      return { name: 'pii_detection', passed: true, details: 'No PII detected' };
    }
    const types = [...new Set(matches.map((m) => m.type))];
    return {
      name: 'pii_detection',
      passed: false,
      details: `Found ${matches.length} PII instance(s): ${types.join(', ')}`,
      findings: types,
    };
  }

  /** Prompt injection detection check. */
  private checkPromptInjection(text: string): CheckResult {
    const matches = detectPromptInjection(text);
    if (matches.length === 0) {
      return { name: 'prompt_injection', passed: true, details: 'No injection patterns detected' };
    }
    const names = matches.map((m) => m.name);
    return {
      name: 'prompt_injection',
      passed: false,
      details: `Found ${matches.length} injection pattern(s): ${names.join(', ')}`,
      findings: names,
    };
  }

  /** Content filter check. */
  private checkContentFilter(text: string): CheckResult {
    const matches = detectDangerousContent(text);
    if (matches.length === 0) {
      return { name: 'content_filter', passed: true, details: 'No dangerous content detected' };
    }
    const names = matches.map((m) => m.name);
    return {
      name: 'content_filter',
      passed: false,
      details: `Found ${matches.length} dangerous pattern(s): ${names.join(', ')}`,
      findings: names,
    };
  }

  /** Cedar policy evaluation — calls platform API or evaluates inline. */
  private async evaluateCedarPolicies(
    data: Record<string, unknown>,
    priorChecks: CheckResult[],
  ): Promise<CheckResult> {
    if (this.config.policySource === 'inline' && !this.config.inlineCedarDsl?.trim()) {
      return { name: 'cedar_policy', passed: true, details: 'No inline Cedar policy configured' };
    }

    if (this.config.policySource === 'platform') {
      return this.evaluatePlatformCedar(data, priorChecks);
    }

    return this.evaluateInlineCedar(data, priorChecks);
  }

  /** Evaluate against Cedar policies fetched from the platform. */
  private async evaluatePlatformCedar(
    data: Record<string, unknown>,
    priorChecks: CheckResult[],
  ): Promise<CheckResult> {
    try {
      const context = this.buildCedarContext(data, priorChecks);

      const res = await fetch(`${this.config.platformUrl}/api/v1/cedar/evaluate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.config.apiKey}`,
        },
        body: JSON.stringify({
          principal: { type: 'n8n::Agent', id: this.config.agentName },
          action: { type: 'n8n::Action', id: 'process_data' },
          resource: { type: 'n8n::WorkflowData', id: 'input' },
          context,
        }),
      });

      if (!res.ok) {
        return {
          name: 'cedar_policy',
          passed: true,
          details: `Platform returned ${res.status} — failing open`,
        };
      }

      const result = (await res.json()) as {
        decision?: string;
        diagnostic?: { reasons?: string[]; errors?: string[] };
      };

      const decision = (result.decision ?? 'allow').toLowerCase();
      if (decision === 'deny') {
        const reasons = result.diagnostic?.reasons ?? ['Policy denied the request'];
        return {
          name: 'cedar_policy',
          passed: false,
          details: reasons.join('; '),
          findings: reasons,
        };
      }

      return { name: 'cedar_policy', passed: true, details: 'Cedar policy evaluation passed' };
    } catch {
      // Fail open — platform unreachable
      return {
        name: 'cedar_policy',
        passed: true,
        details: 'Platform unreachable — failing open',
      };
    }
  }

  /** Evaluate inline Cedar DSL against platform's evaluate endpoint. */
  private async evaluateInlineCedar(
    data: Record<string, unknown>,
    priorChecks: CheckResult[],
  ): Promise<CheckResult> {
    try {
      const context = this.buildCedarContext(data, priorChecks);

      const res = await fetch(`${this.config.platformUrl}/api/v1/cedar/evaluate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.config.apiKey}`,
        },
        body: JSON.stringify({
          principal: { type: 'n8n::Agent', id: this.config.agentName },
          action: { type: 'n8n::Action', id: 'process_data' },
          resource: { type: 'n8n::WorkflowData', id: 'input' },
          context,
          inline_policy: this.config.inlineCedarDsl,
        }),
      });

      if (!res.ok) {
        return {
          name: 'cedar_policy',
          passed: true,
          details: `Platform returned ${res.status} — failing open`,
        };
      }

      const result = (await res.json()) as {
        decision?: string;
        diagnostic?: { reasons?: string[]; errors?: string[] };
      };

      const decision = (result.decision ?? 'allow').toLowerCase();
      if (decision === 'deny') {
        const reasons = result.diagnostic?.reasons ?? ['Inline policy denied the request'];
        return {
          name: 'cedar_policy',
          passed: false,
          details: reasons.join('; '),
          findings: reasons,
        };
      }

      return { name: 'cedar_policy', passed: true, details: 'Inline Cedar policy passed' };
    } catch {
      return {
        name: 'cedar_policy',
        passed: true,
        details: 'Platform unreachable — failing open',
      };
    }
  }

  /** Build Cedar evaluation context from input data + prior check results. */
  private buildCedarContext(
    data: Record<string, unknown>,
    priorChecks: CheckResult[],
  ): Record<string, unknown> {
    const piiCheck = priorChecks.find((c) => c.name === 'pii_detection');
    const injectionCheck = priorChecks.find((c) => c.name === 'prompt_injection');
    const contentCheck = priorChecks.find((c) => c.name === 'content_filter');

    const context: Record<string, unknown> = {
      pii_detected: piiCheck ? !piiCheck.passed : false,
      pii_types: piiCheck?.findings ?? [],
      injection_detected: injectionCheck ? !injectionCheck.passed : false,
      content_filter_triggered: contentCheck ? !contentCheck.passed : false,
      data_keys: Object.keys(data),
      data_size: JSON.stringify(data).length,
    };

    // Truncate context to max size
    const contextStr = JSON.stringify(context);
    if (contextStr.length > MAX_CONTEXT_SIZE) {
      delete context.data_keys;
    }

    return context;
  }

  /**
   * Recursively extract all string values from an object into a single text blob.
   * Used for PII detection and content filtering.
   */
  private extractTextContent(data: Record<string, unknown>): string {
    const parts: string[] = [];

    function walk(value: unknown): void {
      if (typeof value === 'string') {
        parts.push(value);
      } else if (Array.isArray(value)) {
        for (const item of value) walk(item);
      } else if (value !== null && typeof value === 'object') {
        for (const v of Object.values(value as Record<string, unknown>)) walk(v);
      }
    }

    walk(data);
    return parts.join(' ');
  }
}
