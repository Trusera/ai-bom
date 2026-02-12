/**
 * Risk scoring engine for AI components.
 * Ported from the Python risk_scorer.py.
 */

import { RISK_WEIGHTS, DEPRECATED_MODELS, REMEDIATION_MAP } from './config';
import { AIComponent, RiskAssessment, Severity } from './models';

/** Human-readable descriptions for each risk flag. */
export const FLAG_DESCRIPTIONS: Readonly<Record<string, string>> = {
  hardcoded_api_key: 'Hardcoded API key detected',
  shadow_ai: 'AI dependency not declared in project files',
  internet_facing: 'AI endpoint exposed to internet',
  multi_agent_no_trust: 'Multi-agent system without trust boundaries',
  no_auth: 'AI endpoint without authentication',
  no_rate_limit: 'No rate limiting on AI endpoint',
  deprecated_model: 'Using deprecated AI model',
  no_error_handling: 'No error handling for AI calls',
  unpinned_model: 'Model version not pinned',
  webhook_no_auth: 'n8n webhook without authentication',
  code_http_tools: 'Agent with code execution and HTTP tools',
  mcp_unknown_server: 'MCP client connected to unknown server',
  agent_chain_no_validation: 'Agent-to-agent chain without validation',
  hardcoded_credentials: 'Hardcoded credentials in workflow',
};

/**
 * Score a single AI component based on its flags and model status.
 * Returns a RiskAssessment with a score clamped to [0, 100].
 */
export function scoreComponent(component: AIComponent): RiskAssessment {
  let score = 0;
  const factors: string[] = [];
  const owaspSet = new Set<string>();

  const seenFlags = new Set<string>();
  for (const flag of component.flags) {
    if (seenFlags.has(flag)) continue;
    seenFlags.add(flag);
    const weight = RISK_WEIGHTS[flag];
    if (weight !== undefined) {
      score += weight;
      const description = FLAG_DESCRIPTIONS[flag] || flag.replace(/_/g, ' ');
      factors.push(`${description} (+${weight})`);
    }
    const entry = REMEDIATION_MAP[flag];
    if (entry) {
      owaspSet.add(`${entry.owaspCategory}: ${entry.owaspCategoryName}`);
    }
  }

  // Fallback: check deprecated model even if not in flags (backwards compat)
  if (
    component.modelName &&
    DEPRECATED_MODELS.has(component.modelName) &&
    !seenFlags.has('deprecated_model')
  ) {
    const weight = RISK_WEIGHTS['deprecated_model'] || 0;
    if (weight > 0) {
      score += weight;
      const description =
        FLAG_DESCRIPTIONS['deprecated_model'] || 'Using deprecated AI model';
      factors.push(`${description} (+${weight})`);
    }
    const entry = REMEDIATION_MAP['deprecated_model'];
    if (entry) {
      owaspSet.add(`${entry.owaspCategory}: ${entry.owaspCategoryName}`);
    }
  }

  score = Math.min(score, 100);

  let severity: Severity;
  if (score >= 76) severity = Severity.Critical;
  else if (score >= 51) severity = Severity.High;
  else if (score >= 26) severity = Severity.Medium;
  else severity = Severity.Low;

  return { score, severity, factors, owaspCategories: Array.from(owaspSet) };
}
