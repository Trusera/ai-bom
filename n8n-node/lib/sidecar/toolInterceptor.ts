/**
 * Trusera Tool Interceptor — prompt-injection-proof policy enforcement.
 *
 * Monkey-patches BaseTool.prototype.invoke to intercept ALL tool calls
 * before they execute. This runs at the JavaScript runtime level, so
 * no LLM prompt injection can bypass it.
 *
 * Pattern ported from the Python SDK's TruseraLangChainInterceptor
 * (which patches BaseTool._run).
 */

import type { PolicyGateEvaluator } from './policyGate';
import type { SidecarReporter } from './reporter';
import type { EnforcementMode, ToolCallProposal } from './types';

/** The name of our own gate tool — skip intercepting it to avoid infinite loops. */
const GATE_TOOL_NAME = 'trusera_policy_gate';

export class TruseraToolInterceptor {
  private originalInvoke: Function | null = null;
  private installed = false;

  /**
   * Install the monkey-patch on BaseTool.prototype.invoke.
   * After this, ALL tool calls go through policy evaluation before executing.
   */
  install(
    evaluator: PolicyGateEvaluator,
    reporter: SidecarReporter,
    enforcement: EnforcementMode,
  ): void {
    if (this.installed) return;

    let BaseTool: any;
    try {
      BaseTool = require('@langchain/core/tools').BaseTool;
    } catch {
      // @langchain/core not available — skip installation silently
      return;
    }

    this._installOnTarget(BaseTool, evaluator, reporter, enforcement);
  }

  /**
   * Install on a specific target object (for testing without @langchain/core).
   * @internal
   */
  _installOnTarget(
    target: { prototype: { invoke: Function } },
    evaluator: PolicyGateEvaluator,
    reporter: SidecarReporter,
    enforcement: EnforcementMode,
  ): void {
    if (this.installed) return;

    this._target = target;
    this.originalInvoke = target.prototype.invoke;
    const self = this;

    target.prototype.invoke = async function (
      this: any,
      input: unknown,
      config?: unknown,
    ): Promise<unknown> {
      const toolName: string = this.name ?? 'unknown';

      // Don't intercept our own policy gate tool
      if (toolName === GATE_TOOL_NAME) {
        return self.originalInvoke!.call(this, input, config);
      }

      // Build a proposal from the tool call
      const toolArgs: Record<string, unknown> =
        typeof input === 'object' && input !== null
          ? (input as Record<string, unknown>)
          : { raw: String(input) };

      const proposal: ToolCallProposal = {
        toolName,
        toolArgs,
        reasoning: '',
        containsPii: false,
        dataSummary: JSON.stringify(toolArgs).slice(0, 500),
      };

      // Evaluate against policies
      const result = await evaluator.evaluateToolCall(proposal);

      // Report the event (fire-and-forget)
      reporter.track(reporter.createToolCallEvent(result, 'TruseraInterceptor'));
      reporter.flush().catch(() => {});

      // Enforce
      if (result.violations.length > 0) {
        const reasons = result.violations.map((v) => v.reason).join('; ');

        if (enforcement === 'block') {
          throw new Error(`[Trusera] BLOCKED: ${toolName} — ${reasons}`);
        }
        if (enforcement === 'warn') {
          console.warn(`[Trusera] WARNING on ${toolName}: ${reasons}`);
        }
        // log mode: continue silently
      }

      // Call the original invoke
      return self.originalInvoke!.call(this, input, config);
    };

    this.installed = true;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _target: any = null;

  /** Restore the original BaseTool.prototype.invoke. */
  uninstall(): void {
    if (!this.installed || !this.originalInvoke) return;

    const target = this._target ?? (() => {
      try { return require('@langchain/core/tools').BaseTool; } catch { return null; }
    })();

    if (target) {
      target.prototype.invoke = this.originalInvoke;
    }

    this.originalInvoke = null;
    this._target = null;
    this.installed = false;
  }

  /** Whether the interceptor is currently active. */
  isInstalled(): boolean {
    return this.installed;
  }
}
