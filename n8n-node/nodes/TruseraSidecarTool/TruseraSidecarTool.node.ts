import type {
  INodeType,
  INodeTypeDescription,
  ISupplyDataFunctions,
  SupplyData,
} from 'n8n-workflow';
import { NodeConnectionTypes } from 'n8n-workflow';

import { SidecarEvaluator } from '../../lib/sidecar/evaluator';
import { SidecarReporter } from '../../lib/sidecar/reporter';
import type { EnforcementMode, PolicySource } from '../../lib/sidecar/types';

export class TruseraSidecarTool implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Sidecar Tool',
    name: 'truseraSidecarTool',
    icon: 'file:trusera.png',
    group: ['transform'],
    version: 1,
    subtitle: 'AI Agent Security Tool',
    description:
      'Tool for AI Agents to validate actions against Trusera security policies before executing them',
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
          { name: 'Log Only', value: 'log', description: 'Always return info, never throw' },
          { name: 'Warn', value: 'warn', description: 'Return info with warning, never throw' },
          { name: 'Block', value: 'block', description: 'Throw error on violation (stops agent)' },
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
        description: 'Cedar policy DSL to evaluate',
      },
      {
        displayName: 'Enable PII Detection',
        name: 'enablePiiDetection',
        type: 'boolean',
        default: true,
        description: 'Whether to scan for personally identifiable information',
      },
      {
        displayName: 'Enable Prompt Injection Detection',
        name: 'enablePromptInjection',
        type: 'boolean',
        default: true,
        description: 'Whether to detect prompt injection patterns',
      },
      {
        displayName: 'Tool Description',
        name: 'toolDescription',
        type: 'string',
        typeOptions: { rows: 3 },
        default:
          'Check if an action or text complies with security policies. Use this before performing sensitive operations, sending data externally, or when handling user input.',
        description:
          'Description the AI agent sees — controls when the agent decides to call this tool',
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
    const toolDescription = this.getNodeParameter(
      'toolDescription',
      itemIndex,
      'Check if an action or text complies with security policies.',
    ) as string;

    const evaluator = new SidecarEvaluator({
      platformUrl: credentials.platformUrl,
      apiKey: credentials.apiKey,
      enforcementMode,
      policySource,
      agentName,
      enablePiiDetection,
      enablePromptInjection,
      enableContentFilter: false,
      inlineCedarDsl,
      policyCacheTtlMs: 60_000,
    });

    const reporter = new SidecarReporter(
      credentials.platformUrl,
      credentials.apiKey,
      agentName,
    );

    // Lazy require @langchain/core — it's a peer dep, only needed for this tool node.
    // Using require() to avoid TypeScript resolving the module at compile time.
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
      name: 'trusera_policy_check',
      description: toolDescription,
      schema: z.object({
        text: z.string().describe('The text or action to validate against security policies'),
        action_type: z
          .string()
          .optional()
          .describe('Type of action being validated (e.g. "api_call", "data_access", "response")'),
      }),
      func: async ({ text, action_type }: { text: string; action_type?: string }) => {
        const data = { text, action_type: action_type ?? 'unknown' };
        const result = await evaluator.evaluate(data);

        // Report event
        reporter.track(
          reporter.createEvaluationEvent(result, data, 'TruseraSidecarTool'),
        );
        try {
          await reporter.flush();
        } catch {
          // fire and forget
        }

        if (result.violations.length === 0) {
          return JSON.stringify({
            decision: 'allow',
            message: 'Action complies with security policies.',
            checks: result.checks.map((c) => ({ name: c.name, passed: c.passed })),
          });
        }

        const violationResponse = {
          decision: 'deny',
          message: `Policy violation: ${result.violations.map((v) => v.reason).join('; ')}`,
          violations: result.violations,
          recommendation:
            'Do not proceed with this action. Modify the content to comply with policies.',
        };

        if (enforcementMode === 'block') {
          throw new Error(
            `[Trusera] Policy violation — action blocked: ${result.violations.map((v) => v.reason).join('; ')}`,
          );
        }

        return JSON.stringify(violationResponse);
      },
    });

    return { response: tool };
  }
}
