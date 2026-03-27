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
    let connectedModel: any;
    try {
      connectedModel = await this.getInputConnectionData(
        NodeConnectionTypes.AiLanguageModel,
        0,
      );
    } catch (err: any) {
      throw new NodeOperationError(this.getNode(), `Failed to get Chat Model: ${err.message}`);
    }

    // Handle array (n8n may return array of connected models)
    const model = Array.isArray(connectedModel)
      ? connectedModel[connectedModel.length - 1]
      : connectedModel;

    if (!model) {
      throw new NodeOperationError(this.getNode(), 'No Chat Model connected');
    }

    // Get connected tools
    let rawToolData: any;
    try {
      rawToolData = await this.getInputConnectionData(NodeConnectionTypes.AiTool, 0);
    } catch {
      rawToolData = [];
    }
    const connectedTools = Array.isArray(rawToolData) ? rawToolData : [rawToolData].filter(Boolean);

    // ── Fix empty tool schemas ──
    // n8n's N8nTool objects from $fromAI() tools have empty schemas when
    // called from custom agent nodes. The $fromAI() expression doesn't
    // resolve in our context. Fix: extract $fromAI params from the raw
    // node config of connected tool sub-nodes, and rebuild schemas.
    let extractFromAICalls: ((str: string) => any[]) | null = null;
    try {
      extractFromAICalls = require('n8n-workflow').extractFromAICalls;
    } catch { /* not available */ }

    // Get parent tool node configs to extract $fromAI params
    const parentNodes = ('getParentNodes' in this)
      ? (this as any).getParentNodes(this.getNode().name, {
          connectionType: NodeConnectionTypes.AiTool,
          depth: 1,
        })
      : [];

    const processedTools: any[] = [];
    const openAiFunctions: any[] = [];

    for (let idx = 0; idx < connectedTools.length; idx++) {
      const tool = connectedTools[idx];
      const schemaKeys = tool.schema?.shape ? Object.keys(tool.schema.shape) : [];
      const parentNode = parentNodes[idx];

      // Try to access the tool's source node parameters
      // N8nTool has a .context property which is the tool sub-node's execution context
      const toolContext = (tool as any).context;
      const toolNodeParams = toolContext?.getNode?.()?.parameters ?? parentNode?.parameters ?? {};

      if (schemaKeys.length === 0 && extractFromAICalls && Object.keys(toolNodeParams).length > 0) {
        // Schema is empty — extract $fromAI params from the raw node config
        const nodeParams = toolNodeParams;
        const fromAiParams: Array<{ key: string; description: string; type: string }> = [];

        // Scan all parameter values for $fromAI() calls
        const scanForFromAI = (obj: any) => {
          if (typeof obj === 'string' && obj.includes('$fromAI')) {
            try {
              const calls = extractFromAICalls!(obj);
              for (const call of calls) {
                fromAiParams.push({
                  key: call.key ?? call[0] ?? 'input',
                  description: call.description ?? call[1] ?? '',
                  type: call.type ?? call[2] ?? 'string',
                });
              }
            } catch { /* parse error */ }
          } else if (typeof obj === 'object' && obj !== null) {
            for (const val of Object.values(obj)) {
              scanForFromAI(val);
            }
          }
        };
        scanForFromAI(nodeParams);

        // Build OpenAI function definition from extracted params
        const properties: any = {};
        const required: string[] = [];
        // Try multiple keys for description — n8n tools use different param names
        const toolDesc = (
          nodeParams.toolDescription ??
          nodeParams.description ??
          tool.description ??
          tool.name ??
          'A tool'
        ) as string;

        if (fromAiParams.length > 0) {
          for (const param of fromAiParams) {
            properties[param.key] = {
              type: param.type === 'number' ? 'number' : param.type === 'boolean' ? 'boolean' : 'string',
              description: param.description,
            };
            required.push(param.key);
          }
        } else {
          // Fallback: single input parameter
          properties.input = {
            type: 'string',
            description: 'The input to pass to the tool as a JSON string',
          };
          required.push('input');
        }

        processedTools.push(tool);
        openAiFunctions.push({
          type: 'function',
          function: {
            name: tool.name,
            description: toolDesc,
            parameters: { type: 'object', properties, required },
          },
        });
      } else if (schemaKeys.length > 0) {
        // Tool has proper schema — build function def from it
        processedTools.push(tool);
        const props: any = {};
        const req: string[] = [];
        for (const [key, zodField] of Object.entries(tool.schema.shape)) {
          props[key] = {
            type: 'string',
            description: (zodField as any)?._def?.description ?? '',
          };
          if (!(zodField as any)?.isOptional?.()) req.push(key);
        }
        openAiFunctions.push({
          type: 'function',
          function: {
            name: tool.name,
            description: tool.description || 'A tool',
            parameters: { type: 'object', properties: props, required: req },
          },
        });
      } else {
        // Fallback for unknown tools
        processedTools.push(tool);
        openAiFunctions.push({
          type: 'function',
          function: {
            name: tool.name,
            description: tool.description || tool.name || 'A tool',
            parameters: {
              type: 'object',
              properties: { input: { type: 'string', description: 'Tool input' } },
              required: ['input'],
            },
          },
        });
      }
    }

    const toolDebug = openAiFunctions.map((f: any, i: number) => {
      const tool = connectedTools[i];
      const ctx = (tool as any)?.context;
      const nodeP = ctx?.getNode?.()?.parameters;
      return {
        name: f.function.name,
        description: f.function.description?.slice(0, 150),
        paramKeys: Object.keys(f.function.parameters?.properties ?? {}),
        nodeParamKeys: nodeP ? Object.keys(nodeP).join(',') : 'no_context',
      };
    });

    // Bind tools using OpenAI function format
    const modelWithTools = model.bind
      ? model.bind({ tools: openAiFunctions })
      : model;

    // Execute for each input item
    for (let i = 0; i < items.length; i++) {
      const text = this.getNodeParameter('text', i, '') as string;

      const messages: any[] = [
        { role: 'system', content: systemMessage },
        { role: 'user', content: text },
      ];

      const intermediateSteps: any[] = [];
      let finalOutput = '';
      let blocked = false;
      let blockReason = '';

      // ── Manual ReAct Agent Loop ──
      // We control this loop, so we control tool execution.
      for (let iter = 0; iter < maxIterations; iter++) {
        // Call the LLM
        const response = await modelWithTools.invoke(messages);

        // Check if the LLM wants to call tools
        const toolCalls = response.tool_calls ?? response.additional_kwargs?.tool_calls ?? [];

        if (!toolCalls || toolCalls.length === 0) {
          // No tool calls — LLM gave a final answer
          finalOutput = typeof response.content === 'string'
            ? response.content
            : JSON.stringify(response.content);
          break;
        }

        // Add assistant message to history
        messages.push(response);

        // Process each tool call
        for (const toolCall of toolCalls) {
          const toolName = toolCall.name ?? toolCall.function?.name ?? 'unknown';
          const toolArgsRaw = toolCall.args ?? toolCall.function?.arguments ?? '{}';
          let toolArgs: Record<string, unknown>;
          try {
            toolArgs = typeof toolArgsRaw === 'string' ? JSON.parse(toolArgsRaw) : (toolArgsRaw ?? {});
          } catch {
            toolArgs = { raw: String(toolArgsRaw) };
          }
          const callId = toolCall.id ?? `call_${iter}`;

          // Debug: capture raw tool call info
          const rawToolCallDebug = {
            name: toolCall.name,
            fnName: toolCall.function?.name,
            argsType: typeof toolArgsRaw,
            argsKeys: Object.keys(toolArgs),
            argsPreview: JSON.stringify(toolArgs).slice(0, 200),
            callId,
          };

          // ── THE KEY: Policy evaluation BEFORE tool execution ──
          const proposal: ToolCallProposal = {
            toolName,
            toolArgs,
            reasoning: '',
            containsPii: false,
            dataSummary: JSON.stringify(toolArgs).slice(0, 500),
          };

          const policyResult = await gateEvaluator.evaluateToolCall(proposal);

          // Report event
          reporter.track(reporter.createToolCallEvent(policyResult, 'TruseraAgent'));

          if (policyResult.violations.length > 0) {
            const reasons = policyResult.violations.map((v) => v.reason).join('; ');

            if (enforcementMode === 'block') {
              blocked = true;
              blockReason = `[Trusera] BLOCKED: ${toolName} — ${reasons}`;

              // Send error as tool result so the agent knows
              messages.push({
                role: 'tool',
                content: `POLICY VIOLATION — THIS TOOL CALL WAS BLOCKED: ${reasons}. Do NOT retry this action.`,
                tool_call_id: callId,
              });

              intermediateSteps.push({
                tool: toolName,
                input: toolArgs,
                output: `BLOCKED: ${reasons}`,
                blocked: true,
              });

              // Break out of the agent loop
              break;
            }

            if (enforcementMode === 'warn') {
              console.warn(`[Trusera] WARNING on ${toolName}: ${reasons}`);
            }
          }

          if (blocked) break;

          // ── Policy approved — execute the actual tool ──
          const tool = processedTools.find((t: any) => t.name === toolName);
          let toolResult = '';

          if (tool) {
            try {
              // n8n tools (N8nTool/DynamicStructuredTool) expect the invoke arg
              // to match their schema. For tools with empty schemas (from $fromAI),
              // pass args as a JSON string — the tool's func/asDynamicTool wrapper
              // handles parsing internally.
              let invokeArg: any;
              const schemaKeys = tool.schema?.shape ? Object.keys(tool.schema.shape) : [];

              if (schemaKeys.length > 0) {
                // Structured tool — pass object matching schema
                invokeArg = toolArgs;
              } else {
                // Empty schema or DynamicTool — pass JSON string
                invokeArg = JSON.stringify(toolArgs);
              }

              const result = await tool.invoke(invokeArg);
              toolResult = typeof result === 'string' ? result : JSON.stringify(result);
            } catch (err: any) {
              toolResult = `Error: ${err.message}`;
            }
          } else {
            toolResult = `Tool '${toolName}' not found`;
          }

          // Add tool result to messages
          messages.push({
            role: 'tool',
            content: toolResult,
            tool_call_id: callId,
          });

          intermediateSteps.push({
            tool: toolName,
            input: toolArgs,
            output: toolResult.slice(0, 1000),
            blocked: false,
            debug: rawToolCallDebug,
          });
        }

        if (blocked) break;
      }

      // Build output
      if (blocked) {
        returnData.push({
          json: {
            output: blockReason,
            blocked: true,
            intermediateSteps,
            _trusera: {
              agentName,
              enforcement: enforcementMode,
              decision: 'blocked',
              reason: blockReason,
              toolDebug,
            },
          },
          pairedItem: { item: i },
        });
      } else {
        returnData.push({
          json: {
            output: finalOutput,
            blocked: false,
            intermediateSteps,
            _trusera: {
              agentName,
              enforcement: enforcementMode,
              decision: 'allowed',
              toolCallsTotal: intermediateSteps.length,
              toolDebug,
            },
          },
          pairedItem: { item: i },
        });
      }
    }

    // Final flush
    try {
      await reporter.flush();
    } catch {
      // Fire and forget
    }

    return [returnData];
  }
}
