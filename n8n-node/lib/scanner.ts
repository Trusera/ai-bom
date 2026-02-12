/**
 * n8n workflow scanner for detecting AI agents and MCP usage.
 * Ported from the Python n8n_scanner.py.
 */

import { N8N_AI_NODE_TYPES, API_KEY_PATTERNS, DANGEROUS_CODE_PATTERNS, DEPRECATED_MODELS } from './config';
import {
  AIComponent,
  ComponentType,
  UsageType,
  N8nWorkflowInfo,
  ScanResult,
  createComponent,
  createRiskAssessment,
  buildSummary,
  generateId,
} from './models';
import { scoreComponent } from './riskScorer';

/** Raw n8n workflow JSON shape. */
export interface N8nWorkflowData {
  name?: string;
  id?: string;
  nodes: N8nNode[];
  connections: Record<string, unknown>;
  [key: string]: unknown;
}

export interface N8nNode {
  type: string;
  name: string;
  parameters?: Record<string, unknown>;
  credentials?: Record<string, unknown>;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

/** Check whether an object looks like a valid n8n workflow. */
export function isValidWorkflow(data: unknown): data is N8nWorkflowData {
  if (typeof data !== 'object' || data === null) return false;
  const obj = data as Record<string, unknown>;
  return Array.isArray(obj['nodes']) && typeof obj['connections'] === 'object' && obj['connections'] !== null;
}

// ---------------------------------------------------------------------------
// Connection parsing
// ---------------------------------------------------------------------------

/** Parse n8n connections object into a simple node-name -> node-names mapping. */
export function parseConnections(connections: Record<string, unknown>): Record<string, string[]> {
  const result: Record<string, string[]> = {};

  for (const [sourceNode, connectionTypes] of Object.entries(connections)) {
    const connectedNodes = new Set<string>();

    if (typeof connectionTypes === 'object' && connectionTypes !== null) {
      for (const connList of Object.values(connectionTypes as Record<string, unknown>)) {
        if (!Array.isArray(connList)) continue;
        for (const connGroup of connList) {
          if (!Array.isArray(connGroup)) continue;
          for (const conn of connGroup) {
            if (typeof conn === 'object' && conn !== null) {
              const target = (conn as Record<string, unknown>)['node'];
              if (typeof target === 'string') {
                connectedNodes.add(target);
              }
            }
          }
        }
      }
    }

    result[sourceNode] = [...connectedNodes];
  }

  return result;
}

/** Get all outgoing connected node names for a given node. */
function getAllConnectedNodes(nodeName: string, connections: Record<string, unknown>): string[] {
  const connected: string[] = [];
  const connectionTypes = connections[nodeName];
  if (typeof connectionTypes !== 'object' || connectionTypes === null) return connected;

  for (const connList of Object.values(connectionTypes as Record<string, unknown>)) {
    if (!Array.isArray(connList)) continue;
    for (const connGroup of connList) {
      if (!Array.isArray(connGroup)) continue;
      for (const conn of connGroup) {
        if (typeof conn === 'object' && conn !== null) {
          const target = (conn as Record<string, unknown>)['node'];
          if (typeof target === 'string') {
            connected.push(target);
          }
        }
      }
    }
  }

  return connected;
}

// ---------------------------------------------------------------------------
// Trigger detection
// ---------------------------------------------------------------------------

function detectTriggerType(nodes: N8nNode[]): string {
  for (const node of nodes) {
    const nodeType = (node.type ?? '').toLowerCase();
    if (nodeType.includes('webhook')) return 'webhook';
    if (nodeType.includes('schedule') || nodeType.includes('cron')) return 'schedule';
    if (nodeType.includes('trigger') && nodeType.includes('manual')) return 'manual';
  }
  return 'unknown';
}

// ---------------------------------------------------------------------------
// Agent helpers
// ---------------------------------------------------------------------------

function isAgentNode(nodeType: string): boolean {
  return nodeType.toLowerCase().includes('.agent');
}

function extractAgentChains(nodes: N8nNode[], connections: Record<string, string[]>): string[][] {
  const agentNodes = new Set<string>();
  for (const node of nodes) {
    if (isAgentNode(node.type ?? '')) {
      agentNodes.add(node.name ?? '');
    }
  }

  const chains: string[][] = [];

  for (const agent of agentNodes) {
    const chain = [agent];
    let current = agent;

    while (connections[current]) {
      const nextAgents = connections[current].filter((n) => agentNodes.has(n));
      if (nextAgents.length === 0) break;
      const nextAgent = nextAgents[0];
      if (chain.includes(nextAgent)) break;
      chain.push(nextAgent);
      current = nextAgent;
    }

    if (chain.length > 1) {
      chains.push(chain);
    }
  }

  return chains;
}

// ---------------------------------------------------------------------------
// Workflow info extraction
// ---------------------------------------------------------------------------

export function extractWorkflowInfo(workflow: N8nWorkflowData, filePath: string): N8nWorkflowInfo {
  const nodes = workflow.nodes ?? [];
  const nodeTypes = nodes.map((n) => n.type ?? '');
  const connections = parseConnections(workflow.connections ?? {});
  const triggerType = detectTriggerType(nodes);
  const agentChains = extractAgentChains(nodes, connections);

  return {
    workflowName: workflow.name ?? filePath,
    workflowId: typeof workflow.id === 'string' ? workflow.id : '',
    nodes: nodeTypes,
    connections,
    triggerType,
    agentChains,
  };
}

// ---------------------------------------------------------------------------
// Node -> Component mapping
// ---------------------------------------------------------------------------

type ComponentMapping = [ComponentType, UsageType, string];

function mapNodeType(nodeType: string): ComponentMapping | null {
  if (nodeType.includes('.agent')) return [ComponentType.AgentFramework, UsageType.Agent, 'n8n'];

  if (nodeType.includes('.openAi') && !nodeType.includes('.lmChat')) return [ComponentType.LlmProvider, UsageType.Completion, 'OpenAI'];
  if (nodeType.includes('.lmChatOpenAi')) return [ComponentType.LlmProvider, UsageType.Completion, 'OpenAI'];
  if (nodeType.includes('.lmChatAnthropic')) return [ComponentType.LlmProvider, UsageType.Completion, 'Anthropic'];
  if (nodeType.includes('.lmChatGoogleGemini')) return [ComponentType.LlmProvider, UsageType.Completion, 'Google'];
  if (nodeType.includes('.lmChatOllama')) return [ComponentType.LlmProvider, UsageType.Completion, 'Ollama'];
  if (nodeType.includes('.lmChatAzureOpenAi')) return [ComponentType.LlmProvider, UsageType.Completion, 'Azure OpenAI'];
  if (nodeType.includes('.lmChatMistralCloud')) return [ComponentType.LlmProvider, UsageType.Completion, 'Mistral'];
  if (nodeType.includes('.lmChatGroq')) return [ComponentType.LlmProvider, UsageType.Completion, 'Groq'];
  if (nodeType.includes('.lmChatCohere')) return [ComponentType.LlmProvider, UsageType.Completion, 'Cohere'];
  if (nodeType.includes('.lmChatHuggingFace')) return [ComponentType.LlmProvider, UsageType.Completion, 'HuggingFace'];

  if (nodeType.includes('.mcpClientTool')) return [ComponentType.McpClient, UsageType.ToolUse, 'MCP'];

  if (nodeType.includes('.toolHttpRequest')) return [ComponentType.Tool, UsageType.ToolUse, 'n8n'];
  if (nodeType.includes('.toolCode')) return [ComponentType.Tool, UsageType.ToolUse, 'n8n'];
  if (nodeType.includes('.toolWorkflow')) return [ComponentType.Tool, UsageType.ToolUse, 'n8n'];
  if (nodeType.includes('.toolCalculator')) return [ComponentType.Tool, UsageType.ToolUse, 'n8n'];
  if (nodeType.includes('.toolWikipedia')) return [ComponentType.Tool, UsageType.ToolUse, 'n8n'];

  if (nodeType.toLowerCase().includes('embedding')) {
    let provider = 'unknown';
    if (nodeType.includes('OpenAi')) provider = 'OpenAI';
    else if (nodeType.includes('Azure')) provider = 'Azure OpenAI';
    else if (nodeType.includes('Cohere')) provider = 'Cohere';
    else if (nodeType.includes('HuggingFace')) provider = 'HuggingFace';
    else if (nodeType.includes('GoogleGemini')) provider = 'Google';
    else if (nodeType.includes('Ollama')) provider = 'Ollama';
    return [ComponentType.Model, UsageType.Embedding, provider];
  }

  if (nodeType.includes('vectorStore')) {
    let provider = 'unknown';
    if (nodeType.includes('Chroma')) provider = 'ChromaDB';
    else if (nodeType.includes('Pinecone')) provider = 'Pinecone';
    else if (nodeType.includes('Qdrant')) provider = 'Qdrant';
    else if (nodeType.includes('Supabase')) provider = 'Supabase';
    else if (nodeType.includes('InMemory')) provider = 'in-memory';
    else if (nodeType.includes('Weaviate')) provider = 'Weaviate';
    return [ComponentType.Tool, UsageType.Embedding, provider];
  }

  if (nodeType.toLowerCase().includes('chain')) return [ComponentType.AgentFramework, UsageType.Orchestration, 'n8n'];
  if (nodeType.toLowerCase().includes('memory')) return [ComponentType.Tool, UsageType.ToolUse, 'n8n'];

  return null;
}

function extractModelName(parameters: Record<string, unknown>): string {
  const modelKeys = ['model', 'modelId', 'modelName', 'modelVersion'];

  for (const key of modelKeys) {
    const value = parameters[key];
    if (typeof value === 'string') return value;
  }

  const resource = parameters['resource'];
  if (typeof resource === 'object' && resource !== null) {
    for (const key of modelKeys) {
      const value = (resource as Record<string, unknown>)[key];
      if (typeof value === 'string') return value;
    }
  }

  return '';
}

// ---------------------------------------------------------------------------
// Credential detection
// ---------------------------------------------------------------------------

const CREDENTIAL_KEYS = [
  'apiKey', 'api_key', 'token', 'accessToken', 'access_token',
  'secret', 'secretKey', 'secret_key', 'password', 'authToken', 'auth_token',
];

const PLACEHOLDER_VALUES = new Set([
  'your_api_key', 'your-api-key', 'placeholder', 'example',
]);

interface CredentialDetection {
  hasCredentials: boolean;
  hasApiKey: boolean;
}

function detectHardcodedCredentials(parameters: Record<string, unknown>): CredentialDetection {
  let hasCredentials = false;
  let hasApiKey = false;

  for (const key of CREDENTIAL_KEYS) {
    const value = parameters[key];
    if (
      typeof value === 'string' &&
      value.length > 5 &&
      !PLACEHOLDER_VALUES.has(value.toLowerCase())
    ) {
      hasCredentials = true;
    }
  }

  const paramsStr = JSON.stringify(parameters);
  if (API_KEY_PATTERNS.some((p) => p.pattern.test(paramsStr))) {
    hasApiKey = true;
  }

  return { hasCredentials, hasApiKey };
}

// ---------------------------------------------------------------------------
// MCP risk checks
// ---------------------------------------------------------------------------

function checkMcpRisks(parameters: Record<string, unknown>, component: AIComponent): void {
  const urlKeys = ['sseEndpoint', 'sseUrl', 'serverUrl', 'url', 'endpoint'];
  for (const key of urlKeys) {
    const urlValue = parameters[key];
    if (typeof urlValue === 'string' && urlValue) {
      const lower = urlValue.toLowerCase();
      if (!lower.includes('localhost') && !urlValue.includes('127.0.0.1') && !urlValue.includes('::1')) {
        component.flags.push('mcp_unknown_server');
        break;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Node -> AIComponent conversion
// ---------------------------------------------------------------------------

function nodeToComponent(
  node: N8nNode,
  filePath: string,
  workflowInfo: N8nWorkflowInfo,
): AIComponent | null {
  const nodeType = node.type ?? '';
  const nodeName = node.name ?? '';
  const parameters = (node.parameters ?? {}) as Record<string, unknown>;

  const mapping = mapNodeType(nodeType);
  if (!mapping) return null;

  const [compType, usageType, provider] = mapping;
  const modelName = extractModelName(parameters);

  const component = createComponent({
    name: nodeName || nodeType,
    type: compType,
    provider,
    modelName,
    usageType,
    location: {
      filePath,
      contextSnippet: `Workflow: ${workflowInfo.workflowName}, Node: ${nodeName}`,
    },
    metadata: {
      workflow_name: workflowInfo.workflowName,
      workflow_id: workflowInfo.workflowId,
      node_type: nodeType,
      trigger_type: workflowInfo.triggerType,
    },
  });

  const credDetection = detectHardcodedCredentials(parameters);
  if (credDetection.hasApiKey) {
    component.flags.push('hardcoded_api_key');
  } else if (credDetection.hasCredentials) {
    component.flags.push('hardcoded_credentials');
  }

  if (modelName && DEPRECATED_MODELS.has(modelName)) {
    component.flags.push('deprecated_model');
  }

  if (compType === ComponentType.McpClient) {
    checkMcpRisks(parameters, component);
  }

  return component;
}

// ---------------------------------------------------------------------------
// Base-node inspection (non-AI nodes with security risks)
// ---------------------------------------------------------------------------

function inspectBaseNodes(
  workflow: N8nWorkflowData,
  filePath: string,
  workflowInfo: N8nWorkflowInfo,
  components: AIComponent[],
): void {
  const compiledDangerPatterns = DANGEROUS_CODE_PATTERNS.map((p) => new RegExp(p));

  for (const node of workflow.nodes) {
    const nodeType = node.type ?? '';
    const nodeName = node.name ?? '';
    const parameters = (node.parameters ?? {}) as Record<string, unknown>;

    if (N8N_AI_NODE_TYPES.has(nodeType)) continue;

    // Check httpRequest nodes for hardcoded API keys
    if (nodeType === 'n8n-nodes-base.httpRequest') {
      const paramsStr = JSON.stringify(parameters);
      for (const { pattern, provider } of API_KEY_PATTERNS) {
        if (pattern.test(paramsStr)) {
          components.push(
            createComponent({
              name: `${provider} API Key in HTTP Request`,
              type: ComponentType.LlmProvider,
              provider,
              usageType: UsageType.Unknown,
              flags: ['hardcoded_api_key'],
              location: {
                filePath,
                contextSnippet: `Workflow: ${workflowInfo.workflowName}, Node: ${nodeName}`,
              },
              metadata: {
                workflow_name: workflowInfo.workflowName,
                workflow_id: workflowInfo.workflowId,
                node_type: nodeType,
                node_name: nodeName,
                trigger_type: workflowInfo.triggerType,
              },
            }),
          );
          break;
        }
      }
    }

    // Check code nodes for dangerous patterns
    if (nodeType === 'n8n-nodes-base.code') {
      const codeContent =
        (typeof parameters['jsCode'] === 'string' ? parameters['jsCode'] : '') ||
        (typeof parameters['code'] === 'string' ? parameters['code'] : '');

      if (codeContent) {
        for (const dangerPattern of compiledDangerPatterns) {
          if (dangerPattern.test(codeContent)) {
            components.push(
              createComponent({
                name: `Dangerous Code: ${nodeName}`,
                type: ComponentType.Tool,
                provider: 'n8n',
                usageType: UsageType.ToolUse,
                flags: ['code_http_tools'],
                location: {
                  filePath,
                  contextSnippet: `Workflow: ${workflowInfo.workflowName}, Node: ${nodeName}`,
                },
                metadata: {
                  workflow_name: workflowInfo.workflowName,
                  workflow_id: workflowInfo.workflowId,
                  node_type: nodeType,
                  node_name: nodeName,
                  trigger_type: workflowInfo.triggerType,
                },
              }),
            );
            break;
          }
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Workflow-level risks
// ---------------------------------------------------------------------------

function hasInsecureWebhook(nodes: N8nNode[]): boolean {
  for (const node of nodes) {
    if ((node.type ?? '').toLowerCase().includes('webhook')) {
      const auth = (node.parameters ?? {} as Record<string, unknown>)['authentication'] as string | undefined;
      if (auth === undefined || auth === null || auth === 'none') {
        return true;
      }
    }
  }
  return false;
}

/** Get all node names that connect TO a given target node (incoming). */
function getIncomingNodeNames(targetName: string, connections: Record<string, unknown>): string[] {
  const sources: string[] = [];
  for (const [sourceNode, connectionTypes] of Object.entries(connections)) {
    if (typeof connectionTypes !== 'object' || connectionTypes === null) continue;
    for (const connList of Object.values(connectionTypes as Record<string, unknown>)) {
      if (!Array.isArray(connList)) continue;
      for (const connGroup of connList) {
        if (!Array.isArray(connGroup)) continue;
        for (const conn of connGroup) {
          if (typeof conn === 'object' && conn !== null) {
            const target = (conn as Record<string, unknown>)['node'];
            if (target === targetName) {
              sources.push(sourceNode);
            }
          }
        }
      }
    }
  }
  return sources;
}

function checkAgentToolRisks(
  nodes: N8nNode[],
  connections: Record<string, unknown>,
  components: AIComponent[],
): void {
  const nodeMap = new Map<string, N8nNode>();
  for (const node of nodes) {
    nodeMap.set(node.name ?? '', node);
  }

  for (const node of nodes) {
    if (!isAgentNode(node.type ?? '')) continue;
    const nodeName = node.name ?? '';

    // Check both outgoing AND incoming connections
    const outgoing = getAllConnectedNodes(nodeName, connections);
    const incoming = getIncomingNodeNames(nodeName, connections);
    const allConnected = [...new Set([...outgoing, ...incoming])];

    let hasCodeTool = false;
    let hasHttpTool = false;

    for (const connectedName of allConnected) {
      const connectedNode = nodeMap.get(connectedName);
      if (!connectedNode) continue;
      const connType = connectedNode.type ?? '';
      if (connType.includes('.toolCode') || connType === 'n8n-nodes-base.code') hasCodeTool = true;
      if (connType.includes('.toolHttpRequest') || connType === 'n8n-nodes-base.httpRequest') hasHttpTool = true;
    }

    if (hasCodeTool && hasHttpTool) {
      for (const component of components) {
        if (component.type === ComponentType.AgentFramework && component.name === nodeName) {
          component.flags.push('code_http_tools');
        }
      }
    }
  }
}

function checkAgentChainRisks(
  nodes: N8nNode[],
  connections: Record<string, unknown>,
  components: AIComponent[],
): void {
  const nodeMap = new Map<string, N8nNode>();
  for (const node of nodes) {
    nodeMap.set(node.name ?? '', node);
  }

  for (const node of nodes) {
    const nodeType = node.type ?? '';
    if (!nodeType.includes('executeWorkflow')) continue;

    const nodeName = node.name ?? '';
    let hasAgentInput = false;
    let hasAgentOutput = false;

    // Check incoming connections
    for (const [sourceNode, targets] of Object.entries(connections)) {
      if (typeof targets !== 'object' || targets === null) continue;
      for (const connList of Object.values(targets as Record<string, unknown>)) {
        if (!Array.isArray(connList)) continue;
        for (const connGroup of connList) {
          if (!Array.isArray(connGroup)) continue;
          for (const conn of connGroup) {
            if (typeof conn === 'object' && conn !== null && (conn as Record<string, unknown>)['node'] === nodeName) {
              const source = nodeMap.get(sourceNode);
              if (source && isAgentNode(source.type ?? '')) {
                hasAgentInput = true;
              }
            }
          }
        }
      }
    }

    // Check outgoing connections
    const connectedNames = getAllConnectedNodes(nodeName, connections);
    for (const connectedName of connectedNames) {
      const connectedNode = nodeMap.get(connectedName);
      if (connectedNode && isAgentNode(connectedNode.type ?? '')) {
        hasAgentOutput = true;
      }
    }

    if (hasAgentInput && hasAgentOutput) {
      for (const component of components) {
        if (component.type === ComponentType.AgentFramework) {
          component.flags.push('agent_chain_no_validation');
        }
      }
    }
  }
}

/** Known base model names without version pins. */
const UNPINNED_MODEL_NAMES = new Set([
  'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo',
  'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
  'claude-3.5-sonnet', 'claude-3.5-haiku',
  'gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash',
  'mistral-large', 'mistral-medium', 'mistral-small',
  'command-r', 'command-r-plus',
  'llama-3.1-70b', 'llama-3.1-8b',
]);

function checkUnpinnedModel(component: AIComponent): void {
  const model = component.modelName;
  if (!model) {
    if (component.type === ComponentType.LlmProvider) {
      component.flags.push('unpinned_model');
    }
    return;
  }
  if (UNPINNED_MODEL_NAMES.has(model)) {
    component.flags.push('unpinned_model');
  }
}

function hasErrorHandling(workflow: N8nWorkflowData): boolean {
  const settings = workflow['settings'] as Record<string, unknown> | undefined;
  if (settings && typeof settings['errorWorkflow'] === 'string' && settings['errorWorkflow']) {
    return true;
  }
  for (const node of workflow.nodes ?? []) {
    const nodeType = (node.type ?? '').toLowerCase();
    if (nodeType.includes('errortrigger') || nodeType.includes('error')) {
      return true;
    }
    if (node['onError'] && node['onError'] !== 'stopWorkflow') {
      return true;
    }
  }
  return false;
}

function hasAnyWebhook(nodes: N8nNode[]): boolean {
  return nodes.some((node) => (node.type ?? '').toLowerCase().includes('webhook'));
}

function applyWorkflowRisks(workflow: N8nWorkflowData, components: AIComponent[]): void {
  const nodes = workflow.nodes ?? [];
  const connections = workflow.connections ?? {};

  if (hasAnyWebhook(nodes)) {
    for (const component of components) {
      component.flags.push('internet_facing');
    }
  }

  if (hasInsecureWebhook(nodes)) {
    for (const component of components) {
      component.flags.push('webhook_no_auth');
    }
  }

  if (!hasErrorHandling(workflow)) {
    for (const component of components) {
      component.flags.push('no_error_handling');
    }
  }

  for (const component of components) {
    checkUnpinnedModel(component);
  }

  checkAgentToolRisks(nodes, connections, components);
  checkAgentChainRisks(nodes, connections, components);
}

// ---------------------------------------------------------------------------
// Cross-workflow agent chain detection
// ---------------------------------------------------------------------------

function detectCrossWorkflowChains(
  workflows: Map<string, N8nWorkflowInfo>,
  components: AIComponent[],
): void {
  const workflowComponents = new Map<string, AIComponent[]>();

  for (const component of components) {
    const wfName = (component.metadata['workflow_name'] as string) ?? '';
    if (!workflowComponents.has(wfName)) {
      workflowComponents.set(wfName, []);
    }
    workflowComponents.get(wfName)!.push(component);
  }

  for (const workflowInfo of workflows.values()) {
    const wfComps = workflowComponents.get(workflowInfo.workflowName) ?? [];
    const agentCount = wfComps.filter((c) => c.type === ComponentType.AgentFramework).length;

    if (agentCount > 1 && workflowInfo.agentChains.length > 0) {
      for (const component of wfComps) {
        if (
          component.type === ComponentType.AgentFramework &&
          !component.flags.includes('agent_chain_no_validation')
        ) {
          component.flags.push('multi_agent_no_trust');
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Public scan API
// ---------------------------------------------------------------------------

/** Scan a single n8n workflow JSON object and return AI components. */
export function scanWorkflow(
  workflowData: unknown,
  filePath: string,
): AIComponent[] {
  if (!isValidWorkflow(workflowData)) return [];

  const workflowInfo = extractWorkflowInfo(workflowData, filePath);
  const components: AIComponent[] = [];

  // Extract AI components from AI node types
  for (const node of workflowData.nodes) {
    const nodeType = node.type ?? '';
    if (!N8N_AI_NODE_TYPES.has(nodeType)) continue;
    const component = nodeToComponent(node, filePath, workflowInfo);
    if (component) components.push(component);
  }

  // Inspect base nodes for security risks
  inspectBaseNodes(workflowData, filePath, workflowInfo, components);

  // Apply workflow-level risk patterns
  applyWorkflowRisks(workflowData, components);

  // Score all components
  for (const component of components) {
    component.risk = scoreComponent(component);
  }

  return components;
}

/** Scan multiple n8n workflow JSON objects and return a full ScanResult. */
export function scanWorkflows(
  workflows: Array<{ data: unknown; filePath: string }>,
): ScanResult {
  const startTime = Date.now();
  const allComponents: AIComponent[] = [];
  const workflowInfoMap = new Map<string, N8nWorkflowInfo>();

  for (const { data, filePath } of workflows) {
    if (!isValidWorkflow(data)) continue;

    const workflowInfo = extractWorkflowInfo(data, filePath);
    workflowInfoMap.set(filePath, workflowInfo);

    const components: AIComponent[] = [];

    for (const node of data.nodes) {
      const nodeType = node.type ?? '';
      if (!N8N_AI_NODE_TYPES.has(nodeType)) continue;
      const component = nodeToComponent(node, filePath, workflowInfo);
      if (component) components.push(component);
    }

    inspectBaseNodes(data, filePath, workflowInfo, components);
    applyWorkflowRisks(data, components);
    allComponents.push(...components);
  }

  // Cross-workflow chain detection
  detectCrossWorkflowChains(workflowInfoMap, allComponents);

  // Score all components
  for (const component of allComponents) {
    component.risk = scoreComponent(component);
  }

  const elapsed = (Date.now() - startTime) / 1000;

  const result: ScanResult = {
    targetPath: workflows.length === 1 ? workflows[0].filePath : 'multiple',
    scanTimestamp: new Date().toISOString(),
    aiBomVersion: '0.1.0',
    components: allComponents,
    n8nWorkflows: [...workflowInfoMap.values()],
    summary: {
      totalComponents: 0,
      totalFilesScanned: workflows.length,
      byType: {},
      byProvider: {},
      bySeverity: {},
      highestRiskScore: 0,
      scanDurationSeconds: elapsed,
    },
  };

  result.summary = buildSummary(result);
  result.summary.totalFilesScanned = workflows.length;
  result.summary.scanDurationSeconds = elapsed;

  return result;
}
