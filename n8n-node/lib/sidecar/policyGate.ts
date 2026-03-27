/**
 * Policy Gate Evaluator for the Trusera Sidecar v2.
 *
 * Evaluates proposed tool calls against Cedar policies, PII detection,
 * and optional AI-powered "brain mode" analysis.
 *
 * Key difference from SidecarEvaluator: the Cedar action is the TOOL NAME
 * (e.g., "gmail_send_email") not generic "process_data", enabling
 * tool-specific policies.
 */

import type {
  PolicyGateConfig,
  PolicyGateResult,
  ToolCallProposal,
  BrainAnalysis,
  CheckResult,
  Violation,
  CedarPolicy,
} from './types';
import { SidecarEvaluator } from './evaluator';

/** Max policy summaries to include in tool description. */
const MAX_POLICY_SUMMARIES = 8;
/** Max chars per policy summary. */
const MAX_SUMMARY_LENGTH = 200;
/** Max brain input size (chars). */
const MAX_BRAIN_INPUT = 4000;

/** Module-level policy summary cache. */
const policySummaryCache = new Map<string, { summaries: string[]; fetchedAt: number }>();

export class PolicyGateEvaluator {
  private config: PolicyGateConfig;
  private sidecarEvaluator: SidecarEvaluator;

  constructor(config: PolicyGateConfig) {
    this.config = config;
    this.sidecarEvaluator = new SidecarEvaluator(config);
  }

  /** Main entry: evaluate a proposed tool call. */
  async evaluateToolCall(proposal: ToolCallProposal): Promise<PolicyGateResult> {
    const startTime = Date.now();
    const checks: CheckResult[] = [];
    const violations: Violation[] = [];

    // 1. Run PII/injection checks on the tool args (reuse SidecarEvaluator)
    const argsData = typeof proposal.toolArgs === 'string'
      ? { raw: proposal.toolArgs }
      : proposal.toolArgs;
    const baseResult = await this.sidecarEvaluator.evaluate(argsData);
    checks.push(...baseResult.checks.filter((c) => c.name !== 'cedar_policy'));
    violations.push(...baseResult.violations.filter((v) => v.policyName !== 'cedar_policy'));

    // 2. Cedar evaluation with tool-specific context
    const cedarCheck = await this.evaluateToolCedar(proposal, checks);
    checks.push(cedarCheck);
    if (!cedarCheck.passed) {
      violations.push({
        policyName: 'cedar_policy',
        reason: cedarCheck.details,
        severity: 'high',
      });
    }

    // 3. Optional brain mode
    let brainAnalysis: BrainAnalysis | undefined;
    if (this.config.brainMode.enabled && this.config.brainApiKey) {
      const summaries = await this.fetchPolicySummaries();
      brainAnalysis = await this.runBrainAnalysis(proposal, summaries, checks);
      checks.push({
        name: 'brain_analysis',
        passed: brainAnalysis.decision !== 'deny',
        details: brainAnalysis.reasoning,
        findings: brainAnalysis.flaggedConcerns,
      });
      if (brainAnalysis.decision === 'deny') {
        violations.push({
          policyName: 'brain_analysis',
          reason: `AI evaluation: ${brainAnalysis.reasoning}`,
          severity: 'high',
        });
      }
    }

    const durationMs = Date.now() - startTime;
    const allowed = violations.length === 0 || this.config.enforcementMode !== 'block';
    const policySummaries = await this.fetchPolicySummaries().catch(() => []);

    return {
      allowed: violations.length === 0 ? true : allowed,
      enforcement: this.config.enforcementMode,
      violations,
      checks,
      timestamp: new Date().toISOString(),
      durationMs,
      proposal,
      brainAnalysis,
      policySummaries,
    };
  }

  /**
   * Fetch policy summaries from the platform for tool description injection.
   * Returns: ["Block PII Exfiltration: Prevents agents from exporting PII", ...]
   */
  async fetchPolicySummaries(): Promise<string[]> {
    const cacheKey = `${this.config.platformUrl}::${this.config.apiKey.slice(0, 8)}`;
    const cached = policySummaryCache.get(cacheKey);
    if (cached && Date.now() - cached.fetchedAt < this.config.policyCacheTtlMs) {
      return cached.summaries;
    }

    try {
      const res = await fetch(`${this.config.platformUrl}/api/v1/cedar/policies`, {
        headers: { Authorization: `Bearer ${this.config.apiKey}` },
      });
      if (!res.ok) return cached?.summaries ?? [];

      const data = (await res.json()) as { data?: CedarPolicy[] };
      const policies = (data.data ?? []).filter((p) => p.enabled);

      const summaries = policies
        .slice(0, MAX_POLICY_SUMMARIES)
        .map((p) => {
          const desc = p.description.length > MAX_SUMMARY_LENGTH
            ? p.description.slice(0, MAX_SUMMARY_LENGTH) + '...'
            : p.description;
          return `${p.name}: ${desc}`;
        });

      policySummaryCache.set(cacheKey, { summaries, fetchedAt: Date.now() });
      return summaries;
    } catch {
      return cached?.summaries ?? [];
    }
  }

  /** Cedar evaluation with tool-call-specific context. */
  private async evaluateToolCedar(
    proposal: ToolCallProposal,
    priorChecks: CheckResult[],
  ): Promise<CheckResult> {
    try {
      const piiCheck = priorChecks.find((c) => c.name === 'pii_detection');
      const injectionCheck = priorChecks.find((c) => c.name === 'prompt_injection');

      const context: Record<string, unknown> = {
        tool_name: proposal.toolName,
        tool_args_keys: Object.keys(proposal.toolArgs),
        pii_detected: piiCheck ? !piiCheck.passed : false,
        pii_types: piiCheck?.findings ?? [],
        injection_detected: injectionCheck ? !injectionCheck.passed : false,
        contains_pii_self_reported: proposal.containsPii,
        data_summary: proposal.dataSummary.slice(0, 500),
        reasoning: proposal.reasoning.slice(0, 500),
        data_size: JSON.stringify(proposal.toolArgs).length,
      };

      const res = await fetch(`${this.config.platformUrl}/api/v1/cedar/evaluate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.config.apiKey}`,
        },
        body: JSON.stringify({
          principal: { type: 'n8n::Agent', id: this.config.agentName },
          action: { type: 'n8n::Action', id: proposal.toolName },
          resource: { type: 'n8n::ToolCall', id: proposal.toolName },
          context,
        }),
      });

      if (!res.ok) {
        return { name: 'cedar_policy', passed: true, details: `Platform returned ${res.status} — failing open` };
      }

      const result = (await res.json()) as {
        decision?: string;
        diagnostic?: { reasons?: string[]; errors?: string[] };
      };

      const decision = (result.decision ?? 'allow').toLowerCase();
      if (decision === 'deny') {
        const reasons = result.diagnostic?.reasons ?? [`Policy denied tool: ${proposal.toolName}`];
        return { name: 'cedar_policy', passed: false, details: reasons.join('; '), findings: reasons };
      }

      return { name: 'cedar_policy', passed: true, details: 'Cedar policy passed for tool call' };
    } catch {
      return { name: 'cedar_policy', passed: true, details: 'Platform unreachable — failing open' };
    }
  }

  /** Brain mode: LLM-powered contextual policy evaluation. */
  async runBrainAnalysis(
    proposal: ToolCallProposal,
    policySummaries: string[],
    priorChecks: CheckResult[],
  ): Promise<BrainAnalysis> {
    const startTime = Date.now();
    try {
      const baseUrl = (this.config.brainBaseUrl ?? 'https://api.openai.com/v1').replace(/\/+$/, '');
      const model = this.config.brainMode.model ?? 'gpt-4o-mini';

      const checksText = priorChecks
        .map((c) => `- ${c.name}: ${c.passed ? 'PASS' : 'FAIL'} — ${c.details}`)
        .join('\n');

      const policiesText = policySummaries.length > 0
        ? policySummaries.map((s, i) => `${i + 1}. ${s}`).join('\n')
        : 'No specific policies configured.';

      const userPrompt = [
        `Tool: ${proposal.toolName}`,
        `Arguments: ${JSON.stringify(proposal.toolArgs).slice(0, MAX_BRAIN_INPUT)}`,
        `Reasoning: ${proposal.reasoning}`,
        `Contains PII (self-reported): ${proposal.containsPii}`,
        `Data summary: ${proposal.dataSummary}`,
        '',
        `Prior automated checks:\n${checksText}`,
      ].join('\n');

      const res = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.config.brainApiKey}`,
        },
        body: JSON.stringify({
          model,
          max_tokens: this.config.brainMode.maxTokens ?? 300,
          temperature: this.config.brainMode.temperature ?? 0.1,
          response_format: { type: 'json_object' },
          messages: [
            {
              role: 'system',
              content: `You are a security policy evaluator for AI agents. Evaluate whether the proposed action should be allowed based on active policies.\n\nActive policies:\n${policiesText}\n\nRespond with JSON: {"decision":"allow"|"deny"|"warn","reasoning":"...","confidence":0.0-1.0,"flagged_concerns":["..."]}`,
            },
            { role: 'user', content: userPrompt },
          ],
        }),
      });

      if (!res.ok) {
        return this.brainFailOpen(Date.now() - startTime);
      }

      const data = (await res.json()) as {
        choices?: Array<{ message?: { content?: string } }>;
      };
      const content = data.choices?.[0]?.message?.content ?? '';
      const parsed = JSON.parse(content) as {
        decision?: string;
        reasoning?: string;
        confidence?: number;
        flagged_concerns?: string[];
      };

      return {
        decision: (parsed.decision as 'allow' | 'deny' | 'warn') ?? 'allow',
        reasoning: parsed.reasoning ?? 'No reasoning provided',
        confidence: parsed.confidence ?? 0.5,
        flaggedConcerns: parsed.flagged_concerns ?? [],
        durationMs: Date.now() - startTime,
      };
    } catch {
      return this.brainFailOpen(Date.now() - startTime);
    }
  }

  private brainFailOpen(durationMs: number): BrainAnalysis {
    return {
      decision: 'allow',
      reasoning: 'Brain mode unavailable — failing open',
      confidence: 0,
      flaggedConcerns: [],
      durationMs,
    };
  }
}
