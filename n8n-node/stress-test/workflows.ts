/**
 * 20 stress-test workflows for the Trusera AI-BOM n8n scanner.
 * Organized by risk tier: safe (1-5), medium (6-10), high (11-15), critical (16-20).
 *
 * Each workflow is a valid n8n workflow JSON structure with realistic node configs.
 */

export interface N8nWorkflow {
  name: string;
  nodes: Array<Record<string, unknown>>;
  connections: Record<string, unknown>;
  settings?: Record<string, unknown>;
  active?: boolean;
}

// Helper to create position for nodes
let posX = 200;
function pos(x?: number, y?: number): [number, number] {
  return [x ?? (posX += 200), y ?? 300];
}

// ============================================================================
// SAFE / LOW RISK (Workflows 1-5) — Expected: 0 flags
// ============================================================================

export const workflow01_SafeScheduledLlmChain: N8nWorkflow = {
  name: '01 - Safe Scheduled LLM Chain',
  settings: { errorWorkflow: 'error-handler-workflow' },
  nodes: [
    {
      parameters: { rule: { interval: [{ field: 'hours', hoursInterval: 1 }] } },
      name: 'Schedule Trigger',
      type: 'n8n-nodes-base.scheduleTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'LLM Chain',
      type: '@n8n/n8n-nodes-langchain.chainLlm',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o-2024-08-06' },
      name: 'OpenAI Chat Model',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
  ],
  connections: {
    'Schedule Trigger': { main: [[{ node: 'LLM Chain', type: 'main', index: 0 }]] },
    'OpenAI Chat Model': { ai_languageModel: [[{ node: 'LLM Chain', type: 'ai_languageModel', index: 0 }]] },
  },
};

export const workflow02_SafeRagPipeline: N8nWorkflow = {
  name: '02 - Safe RAG Pipeline',
  settings: { errorWorkflow: 'error-handler-workflow' },
  nodes: [
    {
      parameters: {},
      name: 'Manual Trigger',
      type: 'n8n-nodes-base.manualTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Document Loader',
      type: '@n8n/n8n-nodes-langchain.documentLoaderFile',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { chunkSize: 500, chunkOverlap: 50 },
      name: 'Text Splitter',
      type: '@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter',
      typeVersion: 1,
      position: [600, 300],
    },
    {
      parameters: {},
      name: 'Pinecone Store',
      type: '@n8n/n8n-nodes-langchain.vectorStorePinecone',
      typeVersion: 1,
      position: [800, 300],
    },
    {
      parameters: { model: 'text-embedding-3-small' },
      name: 'OpenAI Embeddings',
      type: '@n8n/n8n-nodes-langchain.embeddingsOpenAi',
      typeVersion: 1,
      position: [800, 500],
    },
    {
      parameters: {},
      name: 'Retrieval QA',
      type: '@n8n/n8n-nodes-langchain.chainRetrievalQa',
      typeVersion: 1,
      position: [1000, 300],
    },
    {
      parameters: { model: 'claude-3-5-sonnet-20241022' },
      name: 'Anthropic Model',
      type: '@n8n/n8n-nodes-langchain.lmChatAnthropic',
      typeVersion: 1,
      position: [1000, 500],
    },
  ],
  connections: {
    'Manual Trigger': { main: [[{ node: 'Document Loader', type: 'main', index: 0 }]] },
    'Document Loader': { main: [[{ node: 'Text Splitter', type: 'main', index: 0 }]] },
    'Text Splitter': { main: [[{ node: 'Pinecone Store', type: 'main', index: 0 }]] },
    'OpenAI Embeddings': { ai_embedding: [[{ node: 'Pinecone Store', type: 'ai_embedding', index: 0 }]] },
    'Pinecone Store': { main: [[{ node: 'Retrieval QA', type: 'main', index: 0 }]] },
    'Anthropic Model': { ai_languageModel: [[{ node: 'Retrieval QA', type: 'ai_languageModel', index: 0 }]] },
  },
};

export const workflow03_SafeChatAgent: N8nWorkflow = {
  name: '03 - Safe Chat Agent + Calculator',
  settings: { errorWorkflow: 'error-handler-workflow' },
  nodes: [
    {
      parameters: {},
      name: 'Chat Trigger',
      type: '@n8n/n8n-nodes-langchain.chatTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gemini-2.0-flash-001' },
      name: 'Gemini Model',
      type: '@n8n/n8n-nodes-langchain.lmChatGoogleGemini',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {},
      name: 'Calculator',
      type: '@n8n/n8n-nodes-langchain.toolCalculator',
      typeVersion: 1,
      position: [600, 500],
    },
    {
      parameters: { sessionIdType: 'customKey', contextWindowLength: 10 },
      name: 'Memory',
      type: '@n8n/n8n-nodes-langchain.memoryBufferWindow',
      typeVersion: 1,
      position: [400, 700],
    },
  ],
  connections: {
    'Chat Trigger': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'Gemini Model': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
    'Calculator': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
    'Memory': { ai_memory: [[{ node: 'Agent', type: 'ai_memory', index: 0 }]] },
  },
};

export const workflow04_SafeEmbeddingPipeline: N8nWorkflow = {
  name: '04 - Safe Embedding Pipeline',
  settings: { errorWorkflow: 'error-handler-workflow' },
  nodes: [
    {
      parameters: { rule: { interval: [{ field: 'hours', hoursInterval: 6 }] } },
      name: 'Schedule Trigger',
      type: 'n8n-nodes-base.scheduleTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: { operation: 'select', table: 'documents' },
      name: 'Postgres',
      type: 'n8n-nodes-base.postgres',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: {},
      name: 'JSON Loader',
      type: '@n8n/n8n-nodes-langchain.documentLoaderJson',
      typeVersion: 1,
      position: [600, 300],
    },
    {
      parameters: { chunkSize: 1000 },
      name: 'Text Splitter',
      type: '@n8n/n8n-nodes-langchain.textSplitterCharacterTextSplitter',
      typeVersion: 1,
      position: [800, 300],
    },
    {
      parameters: {},
      name: 'Qdrant Store',
      type: '@n8n/n8n-nodes-langchain.vectorStoreQdrant',
      typeVersion: 1,
      position: [1000, 300],
    },
    {
      parameters: { model: 'embed-english-v3.0' },
      name: 'Cohere Embeddings',
      type: '@n8n/n8n-nodes-langchain.embeddingsCohere',
      typeVersion: 1,
      position: [1000, 500],
    },
  ],
  connections: {
    'Schedule Trigger': { main: [[{ node: 'Postgres', type: 'main', index: 0 }]] },
    'Postgres': { main: [[{ node: 'JSON Loader', type: 'main', index: 0 }]] },
    'JSON Loader': { main: [[{ node: 'Text Splitter', type: 'main', index: 0 }]] },
    'Text Splitter': { main: [[{ node: 'Qdrant Store', type: 'main', index: 0 }]] },
    'Cohere Embeddings': { ai_embedding: [[{ node: 'Qdrant Store', type: 'ai_embedding', index: 0 }]] },
  },
};

export const workflow05_InternalSummarization: N8nWorkflow = {
  name: '05 - Internal Summarization',
  settings: { errorWorkflow: 'error-handler-workflow' },
  nodes: [
    {
      parameters: {},
      name: 'Manual Trigger',
      type: 'n8n-nodes-base.manualTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Summarization Chain',
      type: '@n8n/n8n-nodes-langchain.chainSummarization',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'llama3.1:8b-instruct-q5_K_M', baseUrl: 'http://localhost:11434' },
      name: 'Ollama Model',
      type: '@n8n/n8n-nodes-langchain.lmChatOllama',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {},
      name: 'JSON Parser',
      type: '@n8n/n8n-nodes-langchain.outputParserJson',
      typeVersion: 1,
      position: [600, 500],
    },
  ],
  connections: {
    'Manual Trigger': { main: [[{ node: 'Summarization Chain', type: 'main', index: 0 }]] },
    'Ollama Model': { ai_languageModel: [[{ node: 'Summarization Chain', type: 'ai_languageModel', index: 0 }]] },
    'JSON Parser': { ai_outputParser: [[{ node: 'Summarization Chain', type: 'ai_outputParser', index: 0 }]] },
  },
};

// ============================================================================
// MEDIUM RISK (Workflows 6-10) — Expected: 1-2 flags each
// ============================================================================

export const workflow06_WebhookLlmNoAuth: N8nWorkflow = {
  name: '06 - Webhook LLM No Auth',
  nodes: [
    {
      parameters: { path: 'ai-chat', authentication: 'none' },
      name: 'Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: { respondWith: 'text' },
      name: 'Respond to Webhook',
      type: 'n8n-nodes-base.respondToWebhook',
      typeVersion: 1,
      position: [600, 300],
    },
  ],
  connections: {
    'Webhook': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'Agent': { main: [[{ node: 'Respond to Webhook', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
  },
};

export const workflow07_UnpinnedMistralAgent: N8nWorkflow = {
  name: '07 - Unpinned Mistral Agent',
  nodes: [
    {
      parameters: {},
      name: 'Manual Trigger',
      type: 'n8n-nodes-base.manualTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'mistral-large' },
      name: 'Mistral Cloud',
      type: '@n8n/n8n-nodes-langchain.lmChatMistralCloud',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {},
      name: 'Wikipedia',
      type: '@n8n/n8n-nodes-langchain.toolWikipedia',
      typeVersion: 1,
      position: [600, 500],
    },
  ],
  connections: {
    'Manual Trigger': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'Mistral Cloud': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
    'Wikipedia': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
  },
};

export const workflow08_MultiLlmNoErrorHandling: N8nWorkflow = {
  name: '08 - Multi-LLM No Error Handling',
  nodes: [
    {
      parameters: { rule: { interval: [{ field: 'hours', hoursInterval: 4 }] } },
      name: 'Schedule Trigger',
      type: 'n8n-nodes-base.scheduleTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'LLM Chain 1',
      type: '@n8n/n8n-nodes-langchain.chainLlm',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o-2024-08-06' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {},
      name: 'LLM Chain 2',
      type: '@n8n/n8n-nodes-langchain.chainLlm',
      typeVersion: 1,
      position: [600, 300],
    },
    {
      parameters: { model: 'claude-3-5-sonnet-20241022' },
      name: 'Anthropic Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatAnthropic',
      typeVersion: 1,
      position: [600, 500],
    },
    {
      parameters: { channel: '#ai-summaries' },
      name: 'Slack',
      type: 'n8n-nodes-base.slack',
      typeVersion: 1,
      position: [800, 300],
    },
  ],
  connections: {
    'Schedule Trigger': { main: [[{ node: 'LLM Chain 1', type: 'main', index: 0 }]] },
    'LLM Chain 1': { main: [[{ node: 'LLM Chain 2', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'LLM Chain 1', type: 'ai_languageModel', index: 0 }]] },
    'LLM Chain 2': { main: [[{ node: 'Slack', type: 'main', index: 0 }]] },
    'Anthropic Chat': { ai_languageModel: [[{ node: 'LLM Chain 2', type: 'ai_languageModel', index: 0 }]] },
  },
};

export const workflow09_McpExternalServer: N8nWorkflow = {
  name: '09 - MCP External Server',
  nodes: [
    {
      parameters: {},
      name: 'Manual Trigger',
      type: 'n8n-nodes-base.manualTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o-2024-08-06' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: { sseEndpoint: 'https://mcp.external.io/sse' },
      name: 'MCP Client',
      type: '@n8n/n8n-nodes-langchain.mcpClientTool',
      typeVersion: 1,
      position: [600, 500],
    },
  ],
  connections: {
    'Manual Trigger': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
    'MCP Client': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
  },
};

export const workflow10_DeprecatedModelAgent: N8nWorkflow = {
  name: '10 - Deprecated Model Agent',
  nodes: [
    {
      parameters: {},
      name: 'Manual Trigger',
      type: 'n8n-nodes-base.manualTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-3.5-turbo-0301' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: { sessionIdType: 'customKey', contextWindowLength: 5 },
      name: 'Memory',
      type: '@n8n/n8n-nodes-langchain.memoryBufferWindow',
      typeVersion: 1,
      position: [600, 500],
    },
  ],
  connections: {
    'Manual Trigger': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
    'Memory': { ai_memory: [[{ node: 'Agent', type: 'ai_memory', index: 0 }]] },
  },
};

// ============================================================================
// HIGH RISK (Workflows 11-15) — Expected: 3+ flags
// ============================================================================

export const workflow11_WebhookAgentCodeHttp: N8nWorkflow = {
  name: '11 - Webhook Agent + Code+HTTP',
  nodes: [
    {
      parameters: { path: 'agent-tools', authentication: 'none' },
      name: 'Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {},
      name: 'Code Tool',
      type: '@n8n/n8n-nodes-langchain.toolCode',
      typeVersion: 1,
      position: [600, 500],
    },
    {
      parameters: {},
      name: 'HTTP Tool',
      type: '@n8n/n8n-nodes-langchain.toolHttpRequest',
      typeVersion: 1,
      position: [800, 500],
    },
    {
      parameters: { respondWith: 'text' },
      name: 'Respond to Webhook',
      type: 'n8n-nodes-base.respondToWebhook',
      typeVersion: 1,
      position: [600, 300],
    },
  ],
  connections: {
    'Webhook': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'Agent': { main: [[{ node: 'Respond to Webhook', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
    'Code Tool': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
    'HTTP Tool': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
  },
};

export const workflow12_MultiAgentChainNoValidation: N8nWorkflow = {
  name: '12 - Multi-Agent Chain No Validation',
  nodes: [
    {
      parameters: { path: 'multi-agent', authentication: 'none' },
      name: 'Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent 1',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o-2024-08-06' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: { workflowId: 'sub-workflow-1' },
      name: 'Execute Workflow',
      type: 'n8n-nodes-base.executeWorkflow',
      typeVersion: 1,
      position: [600, 300],
    },
    {
      parameters: {},
      name: 'Agent 2',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [800, 300],
    },
    {
      parameters: { model: 'claude-3-5-sonnet-20241022' },
      name: 'Anthropic Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatAnthropic',
      typeVersion: 1,
      position: [800, 500],
    },
  ],
  connections: {
    'Webhook': { main: [[{ node: 'Agent 1', type: 'main', index: 0 }]] },
    'Agent 1': { main: [[{ node: 'Execute Workflow', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent 1', type: 'ai_languageModel', index: 0 }]] },
    'Execute Workflow': { main: [[{ node: 'Agent 2', type: 'main', index: 0 }]] },
    'Anthropic Chat': { ai_languageModel: [[{ node: 'Agent 2', type: 'ai_languageModel', index: 0 }]] },
  },
};

export const workflow13_HardcodedApiKey: N8nWorkflow = {
  name: '13 - Hardcoded API Key',
  nodes: [
    {
      parameters: {},
      name: 'Manual Trigger',
      type: 'n8n-nodes-base.manualTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o-2024-08-06', apiKey: 'sk-proj-FAKE1234567890abcdefghij' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {
        url: 'https://api.openai.com/v1/embeddings',
        method: 'POST',
        headerParameters: { parameters: [{ name: 'Authorization', value: 'Bearer sk-proj-ANOTHER1234567890fakekey' }] },
      },
      name: 'HTTP Request',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 1,
      position: [600, 300],
    },
  ],
  connections: {
    'Manual Trigger': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'Agent': { main: [[{ node: 'HTTP Request', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
  },
};

export const workflow14_McpWebhookGroq: N8nWorkflow = {
  name: '14 - MCP + Webhook + Groq Unpinned',
  nodes: [
    {
      parameters: { path: 'groq-mcp', authentication: 'none' },
      name: 'Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'mixtral-8x7b-32768' },
      name: 'Groq Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatGroq',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: { sseEndpoint: 'https://mcp.tools-provider.io/sse' },
      name: 'MCP Client',
      type: '@n8n/n8n-nodes-langchain.mcpClientTool',
      typeVersion: 1,
      position: [600, 500],
    },
    {
      parameters: { respondWith: 'text' },
      name: 'Respond to Webhook',
      type: 'n8n-nodes-base.respondToWebhook',
      typeVersion: 1,
      position: [600, 300],
    },
  ],
  connections: {
    'Webhook': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'Agent': { main: [[{ node: 'Respond to Webhook', type: 'main', index: 0 }]] },
    'Groq Chat': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
    'MCP Client': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
  },
};

export const workflow15_AgentChainDeprecatedModels: N8nWorkflow = {
  name: '15 - Agent Chain + Deprecated Models',
  nodes: [
    {
      parameters: { rule: { interval: [{ field: 'hours', hoursInterval: 12 }] } },
      name: 'Schedule Trigger',
      type: 'n8n-nodes-base.scheduleTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent 1',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4-0613' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: { workflowId: 'sub-workflow-2' },
      name: 'Execute Workflow',
      type: 'n8n-nodes-base.executeWorkflow',
      typeVersion: 1,
      position: [600, 300],
    },
    {
      parameters: {},
      name: 'Agent 2',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [800, 300],
    },
    {
      parameters: { model: 'claude-2.1' },
      name: 'Anthropic Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatAnthropic',
      typeVersion: 1,
      position: [800, 500],
    },
  ],
  connections: {
    'Schedule Trigger': { main: [[{ node: 'Agent 1', type: 'main', index: 0 }]] },
    'Agent 1': { main: [[{ node: 'Execute Workflow', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent 1', type: 'ai_languageModel', index: 0 }]] },
    'Execute Workflow': { main: [[{ node: 'Agent 2', type: 'main', index: 0 }]] },
    'Anthropic Chat': { ai_languageModel: [[{ node: 'Agent 2', type: 'ai_languageModel', index: 0 }]] },
  },
};

// ============================================================================
// CRITICAL RISK (Workflows 16-20) — Expected: max flags, score 76+
// ============================================================================

export const workflow16_HardcodedWebhookCodeHttp: N8nWorkflow = {
  name: '16 - Hardcoded + Webhook + Code/HTTP',
  nodes: [
    {
      parameters: { path: 'critical-agent', authentication: 'none' },
      name: 'Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: { apiKey: 'sk-proj-CRITICAL1234567890abcdefghijklmnop' },
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {},
      name: 'Code Tool',
      type: '@n8n/n8n-nodes-langchain.toolCode',
      typeVersion: 1,
      position: [600, 500],
    },
    {
      parameters: {},
      name: 'HTTP Tool',
      type: '@n8n/n8n-nodes-langchain.toolHttpRequest',
      typeVersion: 1,
      position: [800, 500],
    },
    {
      parameters: { respondWith: 'text' },
      name: 'Respond to Webhook',
      type: 'n8n-nodes-base.respondToWebhook',
      typeVersion: 1,
      position: [600, 300],
    },
  ],
  connections: {
    'Webhook': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'Agent': { main: [[{ node: 'Respond to Webhook', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
    'Code Tool': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
    'HTTP Tool': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
  },
};

export const workflow17_MultiAgentHardcodedMcp: N8nWorkflow = {
  name: '17 - Multi-Agent Hardcoded + MCP',
  nodes: [
    {
      parameters: {},
      name: 'Manual Trigger',
      type: 'n8n-nodes-base.manualTrigger',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: { token: 'sk-ant-FAKE1234567890abcdefghij' },
      name: 'Agent 1',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'claude-3-opus' },
      name: 'Anthropic Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatAnthropic',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: { sseEndpoint: 'https://mcp.untrusted-provider.com/sse' },
      name: 'MCP Client',
      type: '@n8n/n8n-nodes-langchain.mcpClientTool',
      typeVersion: 1,
      position: [600, 500],
    },
    {
      parameters: {},
      name: 'Agent 2',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [800, 300],
    },
    {
      parameters: { model: 'gpt-4o', apiKey: 'sk-proj-SECONDFAKE1234567890abcdef' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [800, 500],
    },
  ],
  connections: {
    'Manual Trigger': { main: [[{ node: 'Agent 1', type: 'main', index: 0 }]] },
    'Agent 1': { main: [[{ node: 'Agent 2', type: 'main', index: 0 }]] },
    'Anthropic Chat': { ai_languageModel: [[{ node: 'Agent 1', type: 'ai_languageModel', index: 0 }]] },
    'MCP Client': { ai_tool: [[{ node: 'Agent 1', type: 'ai_tool', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent 2', type: 'ai_languageModel', index: 0 }]] },
  },
};

export const workflow18_FullAttackSurface: N8nWorkflow = {
  name: '18 - Full Attack Surface',
  nodes: [
    {
      parameters: { path: 'full-attack', authentication: 'none' },
      name: 'Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: { apiKey: 'sk-proj-FULLATTACK1234567890abcdefgh' },
      name: 'Agent 1',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-3.5-turbo-0301' },
      name: 'OpenAI Chat Old',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {},
      name: 'Code Tool',
      type: '@n8n/n8n-nodes-langchain.toolCode',
      typeVersion: 1,
      position: [400, 700],
    },
    {
      parameters: {},
      name: 'HTTP Tool',
      type: '@n8n/n8n-nodes-langchain.toolHttpRequest',
      typeVersion: 1,
      position: [600, 700],
    },
    {
      parameters: { sseEndpoint: 'https://mcp.evil.io/sse' },
      name: 'MCP Client',
      type: '@n8n/n8n-nodes-langchain.mcpClientTool',
      typeVersion: 1,
      position: [800, 700],
    },
    {
      parameters: { workflowId: 'sub-attack' },
      name: 'Execute Workflow',
      type: 'n8n-nodes-base.executeWorkflow',
      typeVersion: 1,
      position: [600, 300],
    },
    {
      parameters: {},
      name: 'Agent 2',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [800, 300],
    },
    {
      parameters: { model: 'claude-2.0' },
      name: 'Anthropic Chat Old',
      type: '@n8n/n8n-nodes-langchain.lmChatAnthropic',
      typeVersion: 1,
      position: [800, 500],
    },
    {
      parameters: { respondWith: 'text' },
      name: 'Respond to Webhook',
      type: 'n8n-nodes-base.respondToWebhook',
      typeVersion: 1,
      position: [1000, 300],
    },
  ],
  connections: {
    'Webhook': { main: [[{ node: 'Agent 1', type: 'main', index: 0 }]] },
    'Agent 1': { main: [[{ node: 'Execute Workflow', type: 'main', index: 0 }]] },
    'OpenAI Chat Old': { ai_languageModel: [[{ node: 'Agent 1', type: 'ai_languageModel', index: 0 }]] },
    'Code Tool': { ai_tool: [[{ node: 'Agent 1', type: 'ai_tool', index: 0 }]] },
    'HTTP Tool': { ai_tool: [[{ node: 'Agent 1', type: 'ai_tool', index: 0 }]] },
    'MCP Client': { ai_tool: [[{ node: 'Agent 1', type: 'ai_tool', index: 0 }]] },
    'Execute Workflow': { main: [[{ node: 'Agent 2', type: 'main', index: 0 }]] },
    'Anthropic Chat Old': { ai_languageModel: [[{ node: 'Agent 2', type: 'ai_languageModel', index: 0 }]] },
    'Agent 2': { main: [[{ node: 'Respond to Webhook', type: 'main', index: 0 }]] },
  },
};

export const workflow19_DangerousCodeMcpExfil: N8nWorkflow = {
  name: '19 - Dangerous Code + MCP Exfil',
  nodes: [
    {
      parameters: { path: 'code-exfil', authentication: 'none' },
      name: 'Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: {},
      name: 'Agent',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4o' },
      name: 'OpenAI Chat',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: { sseEndpoint: 'https://mcp.exfil-server.io/sse' },
      name: 'MCP Client',
      type: '@n8n/n8n-nodes-langchain.mcpClientTool',
      typeVersion: 1,
      position: [600, 500],
    },
    {
      parameters: {
        jsCode: 'const { execSync } = require("child_process");\nconst result = eval(items[0].json.code);\nreturn [{ json: { result } }];',
      },
      name: 'Dangerous Code',
      type: 'n8n-nodes-base.code',
      typeVersion: 1,
      position: [600, 700],
    },
    {
      parameters: {
        url: 'https://api.openai.com/v1/chat/completions',
        method: 'POST',
        headerParameters: { parameters: [{ name: 'Authorization', value: 'Bearer sk-proj-EXFILKEY1234567890abcdef' }] },
      },
      name: 'HTTP Request',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 1,
      position: [800, 300],
    },
    {
      parameters: { respondWith: 'text' },
      name: 'Respond to Webhook',
      type: 'n8n-nodes-base.respondToWebhook',
      typeVersion: 1,
      position: [1000, 300],
    },
  ],
  connections: {
    'Webhook': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'Agent': { main: [[{ node: 'HTTP Request', type: 'main', index: 0 }]] },
    'OpenAI Chat': { ai_languageModel: [[{ node: 'Agent', type: 'ai_languageModel', index: 0 }]] },
    'MCP Client': { ai_tool: [[{ node: 'Agent', type: 'ai_tool', index: 0 }]] },
    'Dangerous Code': { main: [[{ node: 'Agent', type: 'main', index: 0 }]] },
    'HTTP Request': { main: [[{ node: 'Respond to Webhook', type: 'main', index: 0 }]] },
  },
};

export const workflow20_KitchenSink: N8nWorkflow = {
  name: '20 - Kitchen Sink',
  nodes: [
    {
      parameters: { path: 'kitchen-sink', authentication: 'none' },
      name: 'Webhook',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 1,
      position: [200, 300],
    },
    {
      parameters: { secret: 'gsk_FAKEGROQKEY1234567890abcdefghij' },
      name: 'Agent 1',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [400, 300],
    },
    {
      parameters: { model: 'gpt-4-0314' },
      name: 'OpenAI Chat Deprecated',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [400, 500],
    },
    {
      parameters: {},
      name: 'Code Tool',
      type: '@n8n/n8n-nodes-langchain.toolCode',
      typeVersion: 1,
      position: [400, 700],
    },
    {
      parameters: {},
      name: 'HTTP Tool',
      type: '@n8n/n8n-nodes-langchain.toolHttpRequest',
      typeVersion: 1,
      position: [600, 700],
    },
    {
      parameters: { sseEndpoint: 'https://mcp.sink-provider.io/sse' },
      name: 'MCP Client',
      type: '@n8n/n8n-nodes-langchain.mcpClientTool',
      typeVersion: 1,
      position: [800, 700],
    },
    {
      parameters: { apiKey: 'hf_FAKEHFTOKEN1234567890abcdef' },
      name: 'Agent 2',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [800, 300],
    },
    {
      parameters: { model: 'gpt-4o-2024-08-06' },
      name: 'OpenAI Chat 2',
      type: '@n8n/n8n-nodes-langchain.lmChatOpenAi',
      typeVersion: 1,
      position: [800, 500],
    },
    {
      parameters: { workflowId: 'sink-sub' },
      name: 'Execute Workflow',
      type: 'n8n-nodes-base.executeWorkflow',
      typeVersion: 1,
      position: [1000, 300],
    },
    {
      parameters: {},
      name: 'Agent 3',
      type: '@n8n/n8n-nodes-langchain.agent',
      typeVersion: 1,
      position: [1200, 300],
    },
    {
      parameters: { model: 'claude-instant-1.2' },
      name: 'Anthropic Chat Deprecated',
      type: '@n8n/n8n-nodes-langchain.lmChatAnthropic',
      typeVersion: 1,
      position: [1200, 500],
    },
    {
      parameters: {
        jsCode: 'const fn = new Function("x", items[0].json.code);\nreturn [{ json: { result: fn(42) } }];',
      },
      name: 'Dangerous Code',
      type: 'n8n-nodes-base.code',
      typeVersion: 1,
      position: [600, 900],
    },
    {
      parameters: {
        url: 'https://api.example.com/data',
        method: 'POST',
        headerParameters: { parameters: [{ name: 'X-API-Key', value: 'sk-proj-SINKFAKE1234567890abcdef' }] },
      },
      name: 'HTTP Request Base',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 1,
      position: [800, 900],
    },
    {
      parameters: { respondWith: 'text' },
      name: 'Respond to Webhook',
      type: 'n8n-nodes-base.respondToWebhook',
      typeVersion: 1,
      position: [1400, 300],
    },
  ],
  connections: {
    'Webhook': { main: [[{ node: 'Agent 1', type: 'main', index: 0 }]] },
    'Agent 1': { main: [[{ node: 'Agent 2', type: 'main', index: 0 }]] },
    'OpenAI Chat Deprecated': { ai_languageModel: [[{ node: 'Agent 1', type: 'ai_languageModel', index: 0 }]] },
    'Code Tool': { ai_tool: [[{ node: 'Agent 1', type: 'ai_tool', index: 0 }]] },
    'HTTP Tool': { ai_tool: [[{ node: 'Agent 1', type: 'ai_tool', index: 0 }]] },
    'MCP Client': { ai_tool: [[{ node: 'Agent 1', type: 'ai_tool', index: 0 }]] },
    'Agent 2': { main: [[{ node: 'Execute Workflow', type: 'main', index: 0 }]] },
    'OpenAI Chat 2': { ai_languageModel: [[{ node: 'Agent 2', type: 'ai_languageModel', index: 0 }]] },
    'Execute Workflow': { main: [[{ node: 'Agent 3', type: 'main', index: 0 }]] },
    'Agent 3': { main: [[{ node: 'Respond to Webhook', type: 'main', index: 0 }]] },
    'Anthropic Chat Deprecated': { ai_languageModel: [[{ node: 'Agent 3', type: 'ai_languageModel', index: 0 }]] },
    'Dangerous Code': { main: [[{ node: 'Agent 1', type: 'main', index: 0 }]] },
    'HTTP Request Base': { main: [[{ node: 'Agent 2', type: 'main', index: 0 }]] },
  },
};

// ============================================================================
// Export all workflows
// ============================================================================

export const ALL_WORKFLOWS: N8nWorkflow[] = [
  workflow01_SafeScheduledLlmChain,
  workflow02_SafeRagPipeline,
  workflow03_SafeChatAgent,
  workflow04_SafeEmbeddingPipeline,
  workflow05_InternalSummarization,
  workflow06_WebhookLlmNoAuth,
  workflow07_UnpinnedMistralAgent,
  workflow08_MultiLlmNoErrorHandling,
  workflow09_McpExternalServer,
  workflow10_DeprecatedModelAgent,
  workflow11_WebhookAgentCodeHttp,
  workflow12_MultiAgentChainNoValidation,
  workflow13_HardcodedApiKey,
  workflow14_McpWebhookGroq,
  workflow15_AgentChainDeprecatedModels,
  workflow16_HardcodedWebhookCodeHttp,
  workflow17_MultiAgentHardcodedMcp,
  workflow18_FullAttackSurface,
  workflow19_DangerousCodeMcpExfil,
  workflow20_KitchenSink,
];
