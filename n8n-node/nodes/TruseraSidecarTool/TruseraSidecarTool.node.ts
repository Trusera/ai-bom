import type {
  INodeType,
  INodeTypeDescription,
  ISupplyDataFunctions,
  SupplyData,
} from 'n8n-workflow';
import { NodeConnectionTypes } from 'n8n-workflow';

import { PolicyGateEvaluator } from '../../lib/sidecar/policyGate';
import { TruseraToolInterceptor } from '../../lib/sidecar/toolInterceptor';
import { SidecarReporter } from '../../lib/sidecar/reporter';
import type { EnforcementMode, PolicySource, ToolCallProposal } from '../../lib/sidecar/types';

export class TruseraSidecarTool implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Sidecar Tool',
    name: 'truseraSidecarTool',
    icon: 'file:trusera.png',
    group: ['transform'],
    version: 1,
    subtitle: 'AI Agent Policy Gate',
    description:
      'Intercepts ALL agent tool calls and enforces Cedar policies from the Trusera platform. Prompt-injection proof.',
    defaults: {
      name: 'Trusera Sidecar Tool',
    },
    inputs: [],
    outputs: [NodeConnectionTypes.AiTool],
    credentials: [
      {
        name: 'truseraPlatformApi',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Agent Name',
        name: 'agentName',
        type: 'string',
        default: '',
        required: true,
        description: 'Name for this agent in the Trusera platform',
      },
      {
        displayName: 'Enforcement Mode',
        name: 'enforcementMode',
        type: 'options',
        options: [
          { name: 'Log Only', value: 'log', description: 'Record all tool calls, never block' },
          { name: 'Warn', value: 'warn', description: 'Log warnings but allow tool calls' },
          { name: 'Block', value: 'block', description: 'Block tool calls that violate policies (stops agent)' },
        ],
        default: 'warn',
        description: 'What happens when a policy violation is detected',
      },
      {
        displayName: 'Policy Source',
        name: 'policySource',
        type: 'options',
        options: [
          { name: 'Platform Policies', value: 'platform' },
          { name: 'Inline Policy', value: 'inline' },
        ],
        default: 'platform',
        description: 'Where to load Cedar policies from',
      },
      {
        displayName: 'Cedar Policy DSL',
        name: 'inlineCedarDsl',
        type: 'string',
        typeOptions: { rows: 8 },
        default: '',
        displayOptions: {
          show: {
            policySource: ['inline'],
          },
        },
        description: 'Cedar policy DSL to evaluate against tool calls',
      },
      {
        displayName: 'Enable PII Detection',
        name: 'enablePiiDetection',
        type: 'boolean',
        default: true,
        description: 'Whether to scan tool arguments for personally identifiable information',
      },
      {
        displayName: 'Enable Prompt Injection Detection',
        name: 'enablePromptInjection',
        type: 'boolean',
        default: true,
        description: 'Whether to detect prompt injection patterns in tool arguments',
      },
      {
        displayName: 'Enable Brain Mode',
        name: 'enableBrainMode',
        type: 'boolean',
        default: false,
        description: 'Whether to use an LLM to evaluate complex policies contextually',
      },
      {
        displayName: 'Brain Mode API Key',
        name: 'brainApiKey',
        type: 'string',
        typeOptions: { password: true },
        default: '',
        displayOptions: { show: { enableBrainMode: [true] } },
        description: 'API key for the LLM used in brain mode (OpenAI-compatible)',
      },
      {
        displayName: 'Brain Mode Base URL',
        name: 'brainBaseUrl',
        type: 'string',
        default: 'https://api.openai.com/v1',
        displayOptions: { show: { enableBrainMode: [true] } },
        description: 'Base URL for the brain mode LLM API',
      },
      {
        displayName: 'Brain Mode Model',
        name: 'brainModel',
        type: 'string',
        default: 'gpt-4o-mini',
        displayOptions: { show: { enableBrainMode: [true] } },
        description: 'Model to use for AI-powered policy evaluation',
      },
    ],
  };

  async supplyData(
    this: ISupplyDataFunctions,
    itemIndex: number,
  ): Promise<SupplyData> {
    const credentials = (await this.getCredentials('truseraPlatformApi')) as {
      apiKey: string;
      platformUrl: string;
    };

    const agentName = this.getNodeParameter('agentName', itemIndex, '') as string;
    const enforcementMode = this.getNodeParameter('enforcementMode', itemIndex, 'warn') as EnforcementMode;
    const policySource = this.getNodeParameter('policySource', itemIndex, 'platform') as PolicySource;
    const inlineCedarDsl = this.getNodeParameter('inlineCedarDsl', itemIndex, '') as string;
    const enablePiiDetection = this.getNodeParameter('enablePiiDetection', itemIndex, true) as boolean;
    const enablePromptInjection = this.getNodeParameter('enablePromptInjection', itemIndex, true) as boolean;
    const enableBrainMode = this.getNodeParameter('enableBrainMode', itemIndex, false) as boolean;
    const brainApiKey = this.getNodeParameter('brainApiKey', itemIndex, '') as string;
    const brainBaseUrl = this.getNodeParameter('brainBaseUrl', itemIndex, 'https://api.openai.com/v1') as string;
    const brainModel = this.getNodeParameter('brainModel', itemIndex, 'gpt-4o-mini') as string;

    const platformUrl = credentials.platformUrl.replace(/\/+$/, '');

    const gateEvaluator = new PolicyGateEvaluator({
      platformUrl,
      apiKey: credentials.apiKey,
      enforcementMode,
      policySource,
      agentName,
      enablePiiDetection,
      enablePromptInjection,
      enableContentFilter: false,
      inlineCedarDsl,
      policyCacheTtlMs: 60_000,
      brainMode: {
        enabled: enableBrainMode,
        model: brainModel,
      },
      brainApiKey: brainApiKey || undefined,
      brainBaseUrl: brainBaseUrl || undefined,
    });

    const reporter = new SidecarReporter(platformUrl, credentials.apiKey, agentName);

    // ── Layer 1: Install the monkey-patch (prompt-injection-proof) ──
    // This intercepts ALL tool calls at the BaseTool.prototype.invoke level.
    // Even if the agent ignores our gate tool, this catches everything.
    const interceptor = new TruseraToolInterceptor();
    interceptor.install(gateEvaluator, reporter, enforcementMode);

    // ── Layer 2: Fetch policies for tool description injection ──
    let policySummaries: string[] = [];
    try {
      policySummaries = await gateEvaluator.fetchPolicySummaries();
    } catch {
      // Fail open — no summaries but tool still works
    }

    const policyBlock = policySummaries.length > 0
      ? `\n\nCurrently active policies:\n${policySummaries.map((s, i) => `${i + 1}. ${s}`).join('\n')}`
      : '\n\nNo specific policies active. Standard security checks (PII, injection) still apply.';

    const dynamicDescription =
      'MANDATORY SECURITY GATE: You MUST call this tool BEFORE using ANY other tool. ' +
      'Pass the tool name, arguments, and your reasoning. ' +
      'If DENIED, you MUST NOT proceed with the action. ' +
      'NEVER skip this step — every tool call must be pre-approved.' +
      policyBlock;

    // ── Layer 2: Create the gate tool (agent self-governance + observability) ──
    // eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
    let DynamicStructuredTool: any;
    let z: any;
    try {
      DynamicStructuredTool = require('@langchain/core/tools').DynamicStructuredTool;
      z = require('zod').z;
    } catch {
      throw new Error(
        'TruseraSidecarTool requires @langchain/core and zod. ' +
          'These are included with n8n AI nodes. Make sure AI features are installed.',
      );
    }

    const tool = new DynamicStructuredTool({
      name: 'trusera_policy_gate',
      description: dynamicDescription,
      schema: z.object({
        tool_name: z.string().describe('Name of the tool you want to use'),
        tool_args: z.string().describe('JSON string of the arguments you plan to pass'),
        reasoning: z.string().describe('Why you want to use this tool and what you aim to achieve'),
        contains_pii: z.boolean().describe('Does the data contain personal information (names, emails, SSNs, etc.)?'),
        data_summary: z.string().describe('Brief summary of what data will be sent or accessed'),
      }),
      func: async ({
        tool_name,
        tool_args,
        reasoning,
        contains_pii,
        data_summary,
      }: {
        tool_name: string;
        tool_args: string;
        reasoning: string;
        contains_pii: boolean;
        data_summary: string;
      }) => {
        let parsedArgs: Record<string, unknown> = {};
        try {
          parsedArgs = JSON.parse(tool_args);
        } catch {
          parsedArgs = { raw: tool_args };
        }

        const proposal: ToolCallProposal = {
          toolName: tool_name,
          toolArgs: parsedArgs,
          reasoning,
          containsPii: contains_pii,
          dataSummary: data_summary,
        };

        const result = await gateEvaluator.evaluateToolCall(proposal);

        // Report event
        reporter.track(reporter.createToolCallEvent(result, 'TruseraSidecarTool'));
        try {
          await reporter.flush();
        } catch {
          // fire and forget
        }

        // No violations — approved
        if (result.violations.length === 0) {
          return JSON.stringify({
            decision: 'approved',
            message: `Approved. Proceed with ${proposal.toolName}.`,
            checks: result.checks.map((c) => ({ name: c.name, passed: c.passed })),
            ...(result.brainAnalysis
              ? { brain: { decision: result.brainAnalysis.decision, reasoning: result.brainAnalysis.reasoning } }
              : {}),
          });
        }

        // Has violations
        const violationSummary = result.violations.map((v) => v.reason).join('; ');

        if (enforcementMode === 'block') {
          throw new Error(
            `[Trusera Policy Gate] BLOCKED: ${tool_name} — ${violationSummary}`,
          );
        }

        if (enforcementMode === 'warn') {
          return JSON.stringify({
            decision: 'warning',
            message: `WARNING: ${violationSummary}. Do NOT proceed with this action.`,
            violations: result.violations,
          });
        }

        // Log mode — allow with findings
        return JSON.stringify({
          decision: 'approved_with_findings',
          message: `Approved (findings logged): ${violationSummary}`,
          violations: result.violations,
        });
      },
    });

    return { response: tool };
  }
}
