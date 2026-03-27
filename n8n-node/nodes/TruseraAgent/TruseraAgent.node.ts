import type {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';

import { PolicyGateEvaluator } from '../../lib/sidecar/policyGate';
import { SidecarReporter } from '../../lib/sidecar/reporter';
import type { EnforcementMode, PolicySource, ToolCallProposal } from '../../lib/sidecar/types';

export class TruseraAgent implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Agent',
    name: 'truseraAgent',
    icon: 'file:trusera.png',
    group: ['transform'],
    version: 1,
    subtitle: 'Policy-Enforced AI Agent',
    description:
      'AI Agent with built-in policy enforcement. Intercepts every tool call at the code level — prompt injection proof. Drop-in replacement for the standard AI Agent.',
    defaults: {
      name: 'Trusera Agent',
    },
    inputs: [
      { type: NodeConnectionTypes.Main, displayName: '' },
      {
        type: NodeConnectionTypes.AiLanguageModel,
        displayName: 'Chat Model',
        required: true,
        maxConnections: 1,
      },
      {
        type: NodeConnectionTypes.AiMemory,
        displayName: 'Memory',
        required: false,
        maxConnections: 1,
      },
      {
        type: NodeConnectionTypes.AiTool,
        displayName: 'Tool',
        required: false,
      },
    ],
    outputs: [NodeConnectionTypes.Main],
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
        displayName: 'Prompt',
        name: 'text',
        type: 'string',
        typeOptions: { rows: 4 },
        default: '={{ $json.chatInput }}',
        description: 'The input prompt for the agent',
      },
      {
        displayName: 'System Message',
        name: 'systemMessage',
        type: 'string',
        typeOptions: { rows: 6 },
        default: 'You are a helpful assistant.',
        description: 'System message that sets the agent behavior',
      },
      {
        displayName: 'Enforcement Mode',
        name: 'enforcementMode',
        type: 'options',
        options: [
          { name: 'Log Only', value: 'log', description: 'Record tool calls, never block' },
          { name: 'Warn', value: 'warn', description: 'Log warnings, let tools execute' },
          { name: 'Block', value: 'block', description: 'Block tool calls that violate policies' },
        ],
        default: 'block',
        description: 'What happens when a tool call violates a policy',
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
      },
      {
        displayName: 'Cedar Policy DSL',
        name: 'inlineCedarDsl',
        type: 'string',
        typeOptions: { rows: 6 },
        default: '',
        displayOptions: { show: { policySource: ['inline'] } },
        description: 'Cedar policy DSL for tool call evaluation',
      },
      {
        displayName: 'Enable PII Detection',
        name: 'enablePiiDetection',
        type: 'boolean',
        default: true,
        description: 'Whether to scan tool arguments for PII',
      },
      {
        displayName: 'Enable Prompt Injection Detection',
        name: 'enablePromptInjection',
        type: 'boolean',
        default: true,
        description: 'Whether to detect prompt injection in tool arguments',
      },
      {
        displayName: 'Max Iterations',
        name: 'maxIterations',
        type: 'number',
        default: 10,
        description: 'Maximum number of agent reasoning iterations',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];

    // Lazy-require LangChain (peer deps, available in n8n)
    let createToolCallingAgent: any;
    let AgentExecutor: any;
    let ChatPromptTemplate: any;
    let AIMessage: any;
    let HumanMessage: any;
    let SystemMessage: any;
    try {
      createToolCallingAgent = require('langchain/agents').createToolCallingAgent;
      AgentExecutor = require('langchain/agents').AgentExecutor;
      ChatPromptTemplate = require('@langchain/core/prompts').ChatPromptTemplate;
      AIMessage = require('@langchain/core/messages').AIMessage;
      HumanMessage = require('@langchain/core/messages').HumanMessage;
      SystemMessage = require('@langchain/core/messages').SystemMessage;
    } catch {
      throw new NodeOperationError(
        this.getNode(),
        'Trusera Agent requires langchain and @langchain/core. Make sure n8n AI features are installed.',
      );
    }

    // Get credentials and parameters
    const credentials = (await this.getCredentials('truseraPlatformApi')) as {
      apiKey: string;
      platformUrl: string;
    };
    const agentName = this.getNodeParameter('agentName', 0, '') as string;
    const systemMessage = this.getNodeParameter('systemMessage', 0, '') as string;
    const enforcementMode = this.getNodeParameter('enforcementMode', 0, 'block') as EnforcementMode;
    const policySource = this.getNodeParameter('policySource', 0, 'platform') as PolicySource;
    const inlineCedarDsl = this.getNodeParameter('inlineCedarDsl', 0, '') as string;
    const enablePiiDetection = this.getNodeParameter('enablePiiDetection', 0, true) as boolean;
    const enablePromptInjection = this.getNodeParameter('enablePromptInjection', 0, true) as boolean;
    const maxIterations = this.getNodeParameter('maxIterations', 0, 10) as number;
    const platformUrl = credentials.platformUrl.replace(/\/+$/, '');

    // Create evaluator and reporter
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
      brainMode: { enabled: false },
    });

    const reporter = new SidecarReporter(platformUrl, credentials.apiKey, agentName);

    // Get connected LLM
    const model = (await this.getInputConnectionData(
      NodeConnectionTypes.AiLanguageModel,
      0,
    )) as any;

    if (!model) {
      throw new NodeOperationError(this.getNode(), 'No Chat Model connected');
    }

    // Get connected memory (optional)
    let memory: any;
    try {
      memory = await this.getInputConnectionData(NodeConnectionTypes.AiMemory, 0);
    } catch {
      // No memory connected — that's fine
    }

    // Get connected tools
    const rawTools = ((await this.getInputConnectionData(
      NodeConnectionTypes.AiTool,
      0,
    )) ?? []) as any[];

    const connectedTools = Array.isArray(rawTools) ? rawTools : [rawTools].filter(Boolean);

    // ── THE KEY: Wrap every tool with policy enforcement ──
    // This happens at the code level — no prompt injection can bypass it.
    const wrappedTools = connectedTools.map((tool: any) => {
      const originalInvoke = tool.invoke.bind(tool);
      const toolName = tool.name ?? 'unknown';

      tool.invoke = async (input: any, config?: any) => {
        // Build proposal from the tool call
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
        const result = await gateEvaluator.evaluateToolCall(proposal);

        // Report event
        reporter.track(reporter.createToolCallEvent(result, 'TruseraAgent'));
        reporter.flush().catch(() => {});

        // Enforce
        if (result.violations.length > 0) {
          const reasons = result.violations.map((v) => v.reason).join('; ');

          if (enforcementMode === 'block') {
            throw new Error(`[Trusera] BLOCKED: ${toolName} — ${reasons}`);
          }
          if (enforcementMode === 'warn') {
            console.warn(`[Trusera] WARNING on ${toolName}: ${reasons}`);
          }
        }

        // Call the original tool
        return originalInvoke(input, config);
      };

      return tool;
    });

    // Build prompt
    const prompt = ChatPromptTemplate.fromMessages([
      ['system', systemMessage],
      ['placeholder', '{chat_history}'],
      ['human', '{input}'],
      ['placeholder', '{agent_scratchpad}'],
    ]);

    // Create agent
    const agent = createToolCallingAgent({
      llm: model,
      tools: wrappedTools,
      prompt,
      streamRunnable: false,
    });

    const executor = new AgentExecutor({
      agent,
      tools: wrappedTools,
      maxIterations,
      returnIntermediateSteps: true,
      ...(memory ? { memory } : {}),
    });

    // Execute for each input item
    for (let i = 0; i < items.length; i++) {
      const text = this.getNodeParameter('text', i, '') as string;

      try {
        const result = await executor.invoke({
          input: text,
          chat_history: [],
        });

        returnData.push({
          json: {
            output: result.output,
            intermediateSteps: result.intermediateSteps?.map((step: any) => ({
              tool: step.action?.tool,
              input: step.action?.toolInput,
              output: typeof step.observation === 'string'
                ? step.observation.slice(0, 1000)
                : step.observation,
            })),
            _trusera: {
              agentName,
              enforcement: enforcementMode,
              toolCallsTotal: result.intermediateSteps?.length ?? 0,
            },
          },
          pairedItem: { item: i },
        });
      } catch (error: any) {
        // If the error is from our policy gate, include violation details
        if (error.message?.includes('[Trusera]')) {
          returnData.push({
            json: {
              output: null,
              error: error.message,
              blocked: true,
              _trusera: {
                agentName,
                enforcement: enforcementMode,
                decision: 'blocked',
                reason: error.message,
              },
            },
            pairedItem: { item: i },
          });
        } else {
          throw error;
        }
      }
    }

    // Final flush of events
    try {
      await reporter.flush();
    } catch {
      // Fire and forget
    }

    return [returnData];
  }
}
