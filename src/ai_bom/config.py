"""
AI Bill of Materials Scanner - Configuration Module

This module contains all detection knowledge for identifying AI usage across various
dimensions: packages, endpoints, models, API keys, containers, and risk factors.
"""

from typing import Dict, FrozenSet, List, Set, Tuple

# =============================================================================
# KNOWN AI PACKAGES
# =============================================================================
# Maps import/package names to (provider, usage_type) tuples
# Usage types: completion, orchestration, agent, embedding, tool_use

KNOWN_AI_PACKAGES: Dict[str, Tuple[str, str]] = {
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
}

# =============================================================================
# KNOWN AI ENDPOINTS
# =============================================================================
# List of (url_regex_pattern, provider, usage_type) tuples
# Used to detect AI service calls in network traffic, config files, etc.

KNOWN_AI_ENDPOINTS: List[Tuple[str, str, str]] = [
    # OpenAI
    (r"api\.openai\.com", "OpenAI", "completion"),
    (r"openai\.azure\.com", "Azure OpenAI", "completion"),

    # Anthropic
    (r"api\.anthropic\.com", "Anthropic", "completion"),

    # Google
    (r"generativelanguage\.googleapis\.com", "Google", "completion"),
    (r"aiplatform\.googleapis\.com", "Google Vertex AI", "completion"),

    # Cohere
    (r"api\.cohere\.ai", "Cohere", "completion"),

    # Mistral
    (r"api\.mistral\.ai", "Mistral", "completion"),

    # Replicate
    (r"api\.replicate\.com", "Replicate", "completion"),

    # Together AI
    (r"api\.together\.xyz", "Together", "completion"),

    # HuggingFace
    (r"api-inference\.huggingface\.co", "HuggingFace", "completion"),
    (r"huggingface\.co/api", "HuggingFace", "completion"),

    # AWS Bedrock
    (r"bedrock-runtime\..*\.amazonaws\.com", "AWS Bedrock", "completion"),

    # Ollama (local)
    (r"localhost:11434", "Ollama", "completion"),
    (r"127\.0\.0\.1:11434", "Ollama", "completion"),
]

# =============================================================================
# KNOWN MODEL PATTERNS
# =============================================================================
# List of (regex_pattern, provider) tuples for model name detection
# Used to identify model references in code, configs, and prompts

KNOWN_MODEL_PATTERNS: List[Tuple[str, str]] = [
    # OpenAI GPT models
    (r"gpt-4[o]?(-\w+)*", "OpenAI"),
    (r"gpt-3\.5(-\w+)*", "OpenAI"),
    (r"text-davinci-\d+", "OpenAI"),
    (r"text-curie-\d+", "OpenAI"),
    (r"text-babbage-\d+", "OpenAI"),
    (r"text-ada-\d+", "OpenAI"),
    (r"code-davinci-\d+", "OpenAI"),
    (r"code-cushman-\d+", "OpenAI"),

    # OpenAI Embeddings
    (r"text-embedding-\w+-\d+", "OpenAI"),

    # OpenAI Audio/Vision
    (r"dall-e-\d+", "OpenAI"),
    (r"whisper-\d+", "OpenAI"),
    (r"tts-\d+(-\w+)*", "OpenAI"),

    # Anthropic Claude
    (r"claude-3-\w+(-\w+)*", "Anthropic"),
    (r"claude-2(\.\d+)?", "Anthropic"),
    (r"claude-instant-\d+(\.\d+)?", "Anthropic"),

    # Google Models
    (r"gemini-\w+(-\w+)*", "Google"),
    (r"palm-\d+", "Google"),
    (r"bison-\w+", "Google"),

    # Cohere
    (r"command-\w+(-\w+)*", "Cohere"),
    (r"embed-\w+(-\w+)*", "Cohere"),

    # Mistral
    (r"mistral-\w+(-\w+)*", "Mistral"),
    (r"mixtral-\w+(-\w+)*", "Mistral"),

    # Meta LLaMA
    (r"llama-\d+(-\w+)*", "Meta"),
    (r"codellama-\w+(-\w+)*", "Meta"),

    # Microsoft Phi
    (r"phi-\d+(-\w+)*", "Microsoft"),
]

# =============================================================================
# API KEY PATTERNS
# =============================================================================
# List of (regex_pattern, provider) tuples for API key detection
# Used to identify hardcoded credentials and security risks

API_KEY_PATTERNS: List[Tuple[str, str]] = [
    # OpenAI (sk-proj- keys allow hyphens, must check before generic sk- pattern)
    (r"sk-proj-[a-zA-Z0-9_-]{20,}", "OpenAI"),
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI"),

    # Anthropic
    (r"sk-ant-[a-zA-Z0-9-]{20,}", "Anthropic"),

    # HuggingFace
    (r"hf_[a-zA-Z0-9]{20,}", "HuggingFace"),

    # Cohere
    (r"key-[a-zA-Z0-9]{20,}", "Cohere"),

    # Groq
    (r"gsk_[a-zA-Z0-9]{20,}", "Groq"),

    # Replicate
    (r"r8_[a-zA-Z0-9]{20,}", "Replicate"),

    # xAI
    (r"xai-[a-zA-Z0-9]{20,}", "xAI"),

    # Google
    (r"AIza[a-zA-Z0-9_-]{20,}", "Google"),
]

# =============================================================================
# AI DOCKER IMAGES
# =============================================================================
# List of known AI container image prefixes
# Used to detect AI services in Docker/Kubernetes deployments

AI_DOCKER_IMAGES: List[str] = [
    "ollama/ollama",
    "vllm/vllm-openai",
    "ghcr.io/huggingface",
    "nvcr.io/nvidia",
    "ghcr.io/ggerganov/llama.cpp",
    "chromadb/chroma",
    "qdrant/qdrant",
    "semitechnologies/weaviate",
]

# =============================================================================
# N8N AI NODE TYPES
# =============================================================================
# Set of n8n node type strings indicating AI usage
# Used to detect AI in n8n workflow automation

N8N_AI_NODE_TYPES: Set[str] = {
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

EXCLUDED_DIRS: FrozenSet[str] = frozenset({
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
})

# =============================================================================
# SCANNABLE EXTENSIONS
# =============================================================================
# Maps scanner type to file extensions that should be scanned

SCANNABLE_EXTENSIONS: Dict[str, Set[str]] = {
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
    },
}

# =============================================================================
# RISK WEIGHTS
# =============================================================================
# Maps risk factor flags to severity scores (0-100 scale)
# Higher scores indicate more severe security/operational risks

RISK_WEIGHTS: Dict[str, int] = {
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

DEPRECATED_MODELS: Set[str] = {
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

    # Anthropic deprecated models
    "claude-instant-1",
    "claude-instant-1.2",
    "claude-2.0",
}
