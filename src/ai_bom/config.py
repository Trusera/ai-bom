"""
AI Bill of Materials Scanner - Configuration Module

This module contains all detection knowledge for identifying AI usage across various
dimensions: packages, endpoints, models, API keys, containers, and risk factors.
"""

import re
from re import Pattern

# =============================================================================
# KNOWN AI PACKAGES
# =============================================================================
# Maps import/package names to (provider, usage_type) tuples
# Usage types: completion, orchestration, agent, embedding, tool_use

KNOWN_AI_PACKAGES: dict[str, tuple[str, str]] = {
    # OpenAI
    "openai": ("OpenAI", "completion"),
    "tiktoken": ("OpenAI", "tool_use"),
    # Anthropic
    "anthropic": ("Anthropic", "completion"),
    # Google AI
    "google.generativeai": ("Google", "completion"),
    "google-generativeai": ("Google", "completion"),
    "vertexai": ("Google", "completion"),
    # LangChain Ecosystem
    "langchain": ("LangChain", "orchestration"),
    "langchain_core": ("LangChain", "orchestration"),
    "langchain_openai": ("LangChain", "orchestration"),
    "langchain-openai": ("LangChain", "orchestration"),
    "langchain_anthropic": ("LangChain", "orchestration"),
    "langchain-anthropic": ("LangChain", "orchestration"),
    "langchain_community": ("LangChain", "orchestration"),
    "langchain-community": ("LangChain", "orchestration"),
    "langchain_google_genai": ("LangChain", "orchestration"),
    "langchain-google-genai": ("LangChain", "orchestration"),
    # LangGraph
    "langgraph": ("LangGraph", "orchestration"),
    # LlamaIndex
    "llama_index": ("LlamaIndex", "orchestration"),
    "llama-index": ("LlamaIndex", "orchestration"),
    # CrewAI
    "crewai": ("CrewAI", "agent"),
    # AutoGen
    "autogen": ("AutoGen", "agent"),
    "pyautogen": ("AutoGen", "agent"),
    # HuggingFace
    "transformers": ("HuggingFace", "completion"),
    "huggingface_hub": ("HuggingFace", "completion"),
    "diffusers": ("HuggingFace", "completion"),
    "sentence_transformers": ("HuggingFace", "embedding"),
    "sentence-transformers": ("HuggingFace", "embedding"),
    # Ollama
    "ollama": ("Ollama", "completion"),
    # Cohere
    "cohere": ("Cohere", "completion"),
    # Mistral
    "mistralai": ("Mistral", "completion"),
    # Replicate
    "replicate": ("Replicate", "completion"),
    # Together AI
    "together": ("Together", "completion"),
    # vLLM
    "vllm": ("vLLM", "completion"),
    # Vector Databases / Embedding Stores
    "chromadb": ("ChromaDB", "embedding"),
    "pinecone": ("Pinecone", "embedding"),
    "pinecone-client": ("Pinecone", "embedding"),
    "weaviate-client": ("Weaviate", "embedding"),
    "qdrant-client": ("Qdrant", "embedding"),
    # Model Context Protocol
    "mcp": ("MCP", "tool_use"),
    # Agent-to-Agent
    "a2a": ("A2A", "agent"),
    "a2a-sdk": ("A2A", "agent"),
    # Google Agent Development Kit
    "google.adk": ("Google", "agent"),
    "google-adk": ("Google", "agent"),
    # DeepSeek
    "deepseek": ("DeepSeek", "completion"),
    # AWS Bedrock
    "boto3": ("AWS", "completion"),  # Special: requires additional bedrock service check
    # LiteLLM
    "litellm": ("LiteLLM", "completion"),
    # Microsoft
    "guidance": ("Microsoft", "completion"),
    "semantic_kernel": ("Microsoft", "orchestration"),
    "semantic-kernel": ("Microsoft", "orchestration"),
    # DSPy
    "dspy": ("DSPy", "orchestration"),
    "dspy-ai": ("DSPy", "orchestration"),
    # Java AI SDKs
    "com.theokanning.openai": ("OpenAI", "completion"),
    "dev.langchain4j": ("LangChain4j", "orchestration"),
    "dev.langchain4j.model.openai": ("LangChain4j", "orchestration"),
    "dev.langchain4j.model.anthropic": ("LangChain4j", "orchestration"),
    # Go AI SDKs
    "github.com/sashabaranov/go-openai": ("OpenAI", "completion"),
    "github.com/anthropics/anthropic-sdk-go": ("Anthropic", "completion"),
    # Rust AI SDKs
    "async_openai": ("OpenAI", "completion"),
    "async-openai": ("OpenAI", "completion"),
    "anthropic_sdk": ("Anthropic", "completion"),
    "anthropic-sdk": ("Anthropic", "completion"),
    # JavaScript/TypeScript AI SDKs (npm packages)
    "@anthropic-ai/sdk": ("Anthropic", "completion"),
    "@langchain/google-genai": ("LangChain", "orchestration"),
    "@langchain/openai": ("LangChain", "orchestration"),
    "@langchain/anthropic": ("LangChain", "orchestration"),
    # Ruby AI packages
    "ruby-openai": ("OpenAI", "completion"),
    # .NET AI packages
    "Azure.AI.OpenAI": ("Azure OpenAI", "completion"),
    "Microsoft.SemanticKernel": ("Microsoft", "orchestration"),
    "Mscc.GenerativeAI": ("Google", "completion"),
    # Java/Gradle AI packages
    "com.langchain4j:langchain4j": ("LangChain4j", "orchestration"),
    "spring-ai": ("Spring AI", "orchestration"),
    "com.openai:openai-java": ("OpenAI", "completion"),
}

# =============================================================================
# KNOWN AI ENDPOINTS
# =============================================================================
# List of (compiled_regex_pattern, provider, usage_type) tuples
# Used to detect AI service calls in network traffic, config files, etc.

KNOWN_AI_ENDPOINTS: list[tuple[Pattern[str], str, str]] = [
    # OpenAI
    (re.compile(r"api\.openai\.com"), "OpenAI", "completion"),
    (re.compile(r"openai\.azure\.com"), "Azure OpenAI", "completion"),
    # Anthropic
    (re.compile(r"api\.anthropic\.com"), "Anthropic", "completion"),
    # Google
    (re.compile(r"generativelanguage\.googleapis\.com"), "Google", "completion"),
    (re.compile(r"aiplatform\.googleapis\.com"), "Google Vertex AI", "completion"),
    # Cohere
    (re.compile(r"api\.cohere\.ai"), "Cohere", "completion"),
    # Mistral
    (re.compile(r"api\.mistral\.ai"), "Mistral", "completion"),
    # Replicate
    (re.compile(r"api\.replicate\.com"), "Replicate", "completion"),
    # Together AI
    (re.compile(r"api\.together\.xyz"), "Together", "completion"),
    # HuggingFace
    (re.compile(r"api-inference\.huggingface\.co"), "HuggingFace", "completion"),
    (re.compile(r"huggingface\.co/api"), "HuggingFace", "completion"),
    # AWS Bedrock
    (re.compile(r"bedrock-runtime\..*\.amazonaws\.com"), "AWS Bedrock", "completion"),
    # Ollama (local)
    (re.compile(r"localhost:11434"), "Ollama", "completion"),
    (re.compile(r"127\.0\.0\.1:11434"), "Ollama", "completion"),
    # Agent-to-Agent (A2A)
    (re.compile(r"a2a\.googleapis\.com"), "Google A2A", "agent"),
    # xAI
    (re.compile(r"api\.x\.ai"), "xAI", "completion"),
    # Alibaba
    (re.compile(r"dashscope\.aliyuncs\.com"), "Alibaba", "completion"),
]

# =============================================================================
# KNOWN MODEL PATTERNS
# =============================================================================
# List of (regex_pattern, provider) tuples for model name detection
# Used to identify model references in code, configs, and prompts

KNOWN_MODEL_PATTERNS: list[tuple[Pattern[str], str]] = [
    # OpenAI GPT models
    (re.compile(r"gpt-4[o]?(-\w+)*"), "OpenAI"),
    (re.compile(r"gpt-3\.5(-\w+)*"), "OpenAI"),
    (re.compile(r"text-davinci-\d+"), "OpenAI"),
    (re.compile(r"text-curie-\d+"), "OpenAI"),
    (re.compile(r"text-babbage-\d+"), "OpenAI"),
    (re.compile(r"text-ada-\d+"), "OpenAI"),
    (re.compile(r"code-davinci-\d+"), "OpenAI"),
    (re.compile(r"code-cushman-\d+"), "OpenAI"),
    # OpenAI Embeddings
    (re.compile(r"text-embedding-\w+-\d+"), "OpenAI"),
    # OpenAI Audio/Vision
    (re.compile(r"dall-e-\d+"), "OpenAI"),
    (re.compile(r"whisper-\d+"), "OpenAI"),
    (re.compile(r"tts-\d+(-\w+)*"), "OpenAI"),
    # Anthropic Claude
    (re.compile(r"claude-3-\w+(-\w+)*"), "Anthropic"),
    (re.compile(r"claude-2(\.\d+)?"), "Anthropic"),
    (re.compile(r"claude-instant-\d+(\.\d+)?"), "Anthropic"),
    # Google Models
    (re.compile(r"gemini-\w+(-\w+)*"), "Google"),
    (re.compile(r"palm-\d+"), "Google"),
    (re.compile(r"bison-\w+"), "Google"),
    # Cohere
    (re.compile(r"command-\w+(-\w+)*"), "Cohere"),
    (re.compile(r"embed-\w+(-\w+)*"), "Cohere"),
    # Mistral
    (re.compile(r"mistral-\w+(-\w+)*"), "Mistral"),
    (re.compile(r"mixtral-\w+(-\w+)*"), "Mistral"),
    # Meta LLaMA
    (re.compile(r"llama-\d+(-\w+)*"), "Meta"),
    (re.compile(r"codellama-\w+(-\w+)*"), "Meta"),
    # Microsoft Phi
    (re.compile(r"phi-\d+(-\w+)*"), "Microsoft"),
    # OpenAI latest
    (re.compile(r"gpt-4\.5(-\w+)*"), "OpenAI"),
    (re.compile(r"o[13](-\w+)*"), "OpenAI"),
    # Anthropic Claude 4.x
    (re.compile(r"claude-4(-\w+)*"), "Anthropic"),
    (re.compile(r"claude-4\.5(-\w+)*"), "Anthropic"),
    (re.compile(r"claude-sonnet-4(-\w+)*"), "Anthropic"),
    (re.compile(r"claude-opus-4(-\w+)*"), "Anthropic"),
    (re.compile(r"claude-haiku-4(-\w+)*"), "Anthropic"),
    # Google Gemini 2.x
    (re.compile(r"gemini-2\.\d+(-\w+)*"), "Google"),
    # Meta Llama 4
    (re.compile(r"llama-4(-\w+)*"), "Meta"),
    # DeepSeek
    (re.compile(r"deepseek-\w+(-\w+)*"), "DeepSeek"),
    # Alibaba Qwen
    (re.compile(r"qwen(?:\d+(?:\.\d+)?)*(?:-\w+)*"), "Alibaba"),
    # xAI Grok
    (re.compile(r"grok-(?:\d+(?:\.\d+)?|\w+)(?:-\w+)*"), "xAI"),
]

# =============================================================================
# API KEY PATTERNS
# =============================================================================
# List of (regex_pattern, provider) tuples for API key detection
# Used to identify hardcoded credentials and security risks

API_KEY_PATTERNS: list[tuple[Pattern[str], str]] = [
    # OpenAI (sk-proj- keys allow hyphens, must check before generic sk- pattern)
    (re.compile(r"sk-proj-[a-zA-Z0-9_-]{20,}"), "OpenAI"),
    # Note: DeepSeek also uses sk- prefix, causing overlap with OpenAI pattern.
    # We require 'deepseek' in the surrounding context or variable name.
    (
        re.compile(
            r"(?i)deepseek[_-]?(?:api[_-]?key|token|secret)?[\s'\"\=]+(sk-[a-zA-Z0-9]{20,})"
        ),
        "DeepSeek",
    ),
    # OpenAI fallback
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "OpenAI"),
    # Anthropic
    (re.compile(r"sk-ant-[a-zA-Z0-9-]{20,}"), "Anthropic"),
    # HuggingFace
    (re.compile(r"hf_[a-zA-Z0-9]{20,}"), "HuggingFace"),
    # Cohere
    (re.compile(r"key-[a-zA-Z0-9]{20,}"), "Cohere"),
    # Groq
    (re.compile(r"gsk_[a-zA-Z0-9]{20,}"), "Groq"),
    # Replicate
    (re.compile(r"r8_[a-zA-Z0-9]{20,}"), "Replicate"),
    # xAI
    (re.compile(r"xai-[a-zA-Z0-9]{20,}"), "xAI"),
    # Google
    (re.compile(r"AIza[a-zA-Z0-9_-]{20,}"), "Google"),
    # Fireworks
    (re.compile(r"fw_[a-zA-Z0-9]{20,}"), "Fireworks"),
    # Perplexity
    (re.compile(r"pplx-[a-zA-Z0-9]{20,}"), "Perplexity"),
    # Together AI (64-char hex) - require assignment context to avoid git SHAs
    (
        re.compile(
            r"(?i)(?:api[_-]?key|token|secret|together[_-]?(?:api|key))"
            r"[\s'\"\:=]+([a-f0-9]{64})\b"
        ),
        "Together",
    ),
    # Mistral (32-char alnum) - require assignment context to avoid MD5/UUIDs
    (
        re.compile(
            r"(?i)(?:api[_-]?key|token|secret|mistral[_-]?(?:api|key))"
            r"[\s'\"\:=]+([a-zA-Z0-9]{32})\b"
        ),
        "Mistral",
    ),
]

# =============================================================================
# AI DOCKER IMAGES
# =============================================================================
# List of known AI container image prefixes
# Used to detect AI services in Docker/Kubernetes deployments

AI_DOCKER_IMAGES: list[str] = [
    # Inference Servers
    "ollama/ollama",
    "vllm/vllm-openai",
    "localai/localai",
    # ML Frameworks
    "pytorch/pytorch",
    "tensorflow/tensorflow",
    # HuggingFace
    "ghcr.io/huggingface",
    "huggingface/text-generation-inference",
    "huggingface/transformers-pytorch-gpu",
    "ghcr.io/huggingface/text-generation-inference",
    # NVIDIA Images
    "nvcr.io/nvidia",
    "nvcr.io/nvidia/tritonserver",
    "nvcr.io/nvidia/pytorch",
    "nvcr.io/nvidia/tensorflow",
    "nvcr.io/nvidia/tensorrt",
    # LLM Inference
    "ghcr.io/ggerganov/llama.cpp",
    # Jupyter Notebooks (Data Science & ML)
    "jupyter/datascience-notebook",
    "jupyter/scipy-notebook",
    "jupyter/tensorflow-notebook",
    # Vector Databases
    "chromadb/chroma",
    "qdrant/qdrant",
    "semitechnologies/weaviate",
    "weaviate/weaviate",
    "milvus/milvus",
    "pinecone/pinecone",
    "redis/redis-stack",
    "pgvector/pgvector",
    # ML Ops & Orchestration
    "mlflow/mlflow",
    "ray/ray-ml",
    "apache/airflow",
    "daskdev/dask",
]

# =============================================================================
# N8N AI NODE TYPES
# =============================================================================
# Set of n8n node type strings indicating AI usage
# Used to detect AI in n8n workflow automation

N8N_AI_NODE_TYPES: set[str] = {
    # Agent nodes
    "@n8n/n8n-nodes-langchain.agent",
    # LLM Chat nodes
    "@n8n/n8n-nodes-langchain.lmChatOpenAi",
    "@n8n/n8n-nodes-langchain.lmChatAnthropic",
    "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
    "@n8n/n8n-nodes-langchain.lmChatOllama",
    "@n8n/n8n-nodes-langchain.lmChatAzureOpenAi",
    "@n8n/n8n-nodes-langchain.lmChatMistralCloud",
    "@n8n/n8n-nodes-langchain.lmChatGroq",
    "@n8n/n8n-nodes-langchain.lmChatCohere",
    "@n8n/n8n-nodes-langchain.lmChatHuggingFace",
    # Tool nodes
    "@n8n/n8n-nodes-langchain.mcpClientTool",
    "@n8n/n8n-nodes-langchain.toolHttpRequest",
    "@n8n/n8n-nodes-langchain.toolCode",
    "@n8n/n8n-nodes-langchain.toolWorkflow",
    "@n8n/n8n-nodes-langchain.toolCalculator",
    "@n8n/n8n-nodes-langchain.toolWikipedia",
    # Embedding nodes
    "@n8n/n8n-nodes-langchain.embeddingsOpenAi",
    "@n8n/n8n-nodes-langchain.embeddingsAzureOpenAi",
    "@n8n/n8n-nodes-langchain.embeddingsCohere",
    "@n8n/n8n-nodes-langchain.embeddingsHuggingFaceInference",
    "@n8n/n8n-nodes-langchain.embeddingsGoogleGemini",
    "@n8n/n8n-nodes-langchain.embeddingsOllama",
    # Vector store nodes
    "@n8n/n8n-nodes-langchain.vectorStoreChroma",
    "@n8n/n8n-nodes-langchain.vectorStorePinecone",
    "@n8n/n8n-nodes-langchain.vectorStoreQdrant",
    "@n8n/n8n-nodes-langchain.vectorStoreSupabase",
    "@n8n/n8n-nodes-langchain.vectorStoreInMemory",
    "@n8n/n8n-nodes-langchain.vectorStoreWeaviate",
    # Memory nodes
    "@n8n/n8n-nodes-langchain.memoryBufferWindow",
    "@n8n/n8n-nodes-langchain.memoryPostgresChat",
    "@n8n/n8n-nodes-langchain.memoryChatHistory",
    "@n8n/n8n-nodes-langchain.memoryRedisChat",
    # Output parser nodes
    "@n8n/n8n-nodes-langchain.outputParserStructured",
    "@n8n/n8n-nodes-langchain.outputParserAutofixing",
    "@n8n/n8n-nodes-langchain.outputParserJson",
    # Chain nodes
    "@n8n/n8n-nodes-langchain.chainLlm",
    "@n8n/n8n-nodes-langchain.chainSummarization",
    "@n8n/n8n-nodes-langchain.chainRetrievalQa",
    # Text splitter nodes
    "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
    "@n8n/n8n-nodes-langchain.textSplitterCharacterTextSplitter",
    "@n8n/n8n-nodes-langchain.textSplitterMarkdownTextSplitter",
    # Document loader nodes
    "@n8n/n8n-nodes-langchain.documentLoaderFile",
    "@n8n/n8n-nodes-langchain.documentLoaderJson",
    "@n8n/n8n-nodes-langchain.documentLoaderCsv",
}

# =============================================================================
# EXCLUDED DIRECTORIES
# =============================================================================
# Directories to skip during scanning for performance and accuracy

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        "dist",
        "build",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "egg-info",
        ".eggs",
        ".idea",
        ".vscode",
        "coverage",
        ".coverage",
        "htmlcov",
    }
)

# =============================================================================
# CREWAI FLOW PATTERNS
# =============================================================================
# Maps CrewAI decorator names to their semantic type
# Used to detect CrewAI flow-based agent definitions

CREWAI_FLOW_PATTERNS: dict[str, str] = {
    "@crew": "crew_definition",
    "@agent": "agent_definition",
    "@task": "task_definition",
    "@flow": "flow_definition",
    "@tool": "tool_definition",
}

# =============================================================================
# MCP CONFIG FILES
# =============================================================================
# Known filenames for MCP server configuration

MCP_CONFIG_FILES: set[str] = {
    "mcp.json",
    ".mcp.json",
    "mcp-config.json",
    "claude_desktop_config.json",
}

# =============================================================================
# SCANNABLE EXTENSIONS
# =============================================================================
# Maps scanner type to file extensions that should be scanned

SCANNABLE_EXTENSIONS: dict[str, set[str]] = {
    "code": {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".cs",
    },
    "docker": {
        "Dockerfile",
        ".dockerfile",
        ".yml",
        ".yaml",
    },
    "network": {
        ".env",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
    },
    "cloud": {
        ".tf",
        ".json",
        ".yaml",
        ".yml",
    },
    "deps": {
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "Pipfile",
        "poetry.lock",
        "Cargo.toml",
        "go.mod",
        "Gemfile",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
    },
}

# =============================================================================
# RISK WEIGHTS
# =============================================================================
# Maps risk factor flags to severity scores (0-100 scale)
# Higher scores indicate more severe security/operational risks

RISK_WEIGHTS: dict[str, int] = {
    # Critical risks (25-30 points)
    "hardcoded_api_key": 30,
    "hardcoded_credentials": 30,
    "code_http_tools": 30,  # Agent can execute arbitrary code or HTTP
    "shadow_ai": 25,  # Unauthorized AI usage
    "webhook_no_auth": 25,
    # High risks (15-20 points)
    "internet_facing": 20,
    "multi_agent_no_trust": 20,  # Multiple agents without trust boundaries
    "agent_chain_no_validation": 20,  # Agent chains without input validation
    "mcp_unknown_server": 20,  # MCP server from untrusted source
    # Medium risks (10-15 points)
    "no_auth": 15,
    "no_rate_limit": 10,
    "deprecated_model": 10,
    "no_error_handling": 10,
    # Low risks (5 points)
    "unpinned_model": 5,  # Model version not specified
}

# =============================================================================
# DEPRECATED MODELS
# =============================================================================
# Set of model identifiers that are deprecated or should not be used
# Used to flag technical debt and security risks

DEPRECATED_MODELS: set[str] = {
    # OpenAI deprecated models
    "gpt-3.5-turbo",  # Use gpt-3.5-turbo-0125 or gpt-4o-mini instead
    "gpt-3.5-turbo-0301",
    "gpt-3.5-turbo-0613",
    "text-davinci-003",
    "text-davinci-002",
    "code-davinci-002",
    "text-ada-001",
    "text-babbage-001",
    "text-curie-001",
    "text-embedding-ada-002",  # Use text-embedding-3-small/large instead
    "gpt-4-0314",
    "gpt-4-0613",
    "gpt-4-32k-0314",
    "gpt-4-32k-0613",
    # Anthropic deprecated models
    "claude-instant-1",
    "claude-instant-1.2",
    "claude-2.0",
    "claude-2.1",
    "claude-3-haiku-20240307",
}
