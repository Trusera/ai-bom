"""
LLM Pattern Registry.

Central registry of patterns for detecting AI/LLM SDK usage in Python code.
Each pattern includes import signatures, usage patterns, model extraction regex,
and dependency names for comprehensive detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_bom.models import ComponentType, UsageType


@dataclass
class LLMPattern:
    """
    Pattern definition for detecting AI/LLM SDK usage.

    Attributes:
        sdk_name: Human-readable SDK/framework name
        provider: Provider/vendor name
        component_type: Type of AI component
        usage_type: How the component is used
        import_patterns: List of regex patterns matching import statements
        usage_patterns: List of regex patterns matching API usage
        model_extraction: Optional regex with capture group for model names
        dep_names: Package names in requirements.txt or pyproject.toml
    """

    sdk_name: str
    provider: str
    component_type: ComponentType
    usage_type: UsageType
    import_patterns: list[str] = field(default_factory=list)
    usage_patterns: list[str] = field(default_factory=list)
    model_extraction: str | None = None
    dep_names: list[str] = field(default_factory=list)


# Comprehensive pattern registry for 21 major AI/LLM SDKs and frameworks
LLM_PATTERNS: list[LLMPattern] = [
    # 1. OpenAI (Python, JavaScript, Java, Go, Rust)
    LLMPattern(
        sdk_name="OpenAI",
        provider="OpenAI",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            # Python
            r"from\s+openai\s+import",
            r"import\s+openai",
            r"from\s+openai\b",
            # JavaScript/TypeScript
            r"require\(['\"]openai['\"]\)",
            r"from\s+['\"]openai['\"]",
            # Java
            r"import\s+com\.theokanning\.openai",
            # Go
            r"github\.com/sashabaranov/go-openai",
            # Rust
            r"use\s+async_openai",
        ],
        usage_patterns=[
            r"openai\.ChatCompletion",
            r"client\.chat\.completions\.create",
            r"openai\.Completion",
            r"OpenAI\(\s*\)",
            r"AsyncOpenAI\(",
            # Java
            r"OpenAiService\(",
            r"OpenAiChatModel\b",
            # Go
            r"openai\.NewClient\(",
            r"CreateChatCompletion\(",
        ],
        model_extraction=r"model\s*=\s*[\"']([^\"']+)[\"']",
        dep_names=["openai", "com.theokanning.openai"],
    ),
    # 2. Anthropic (Python, JavaScript, Java, Go, Rust)
    LLMPattern(
        sdk_name="Anthropic",
        provider="Anthropic",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            # Python
            r"from\s+anthropic\s+import",
            r"import\s+anthropic",
            # JavaScript/TypeScript
            r"require\(['\"]@anthropic-ai/sdk['\"]\)",
            r"from\s+['\"]@anthropic-ai/sdk['\"]",
            r"Anthropic\s*=\s*require",
            # Java (LangChain4j)
            r"import\s+dev\.langchain4j\.model\.anthropic",
            # Go
            r"github\.com/anthropics/anthropic-sdk-go",
            # Rust
            r"use\s+anthropic_sdk",
        ],
        usage_patterns=[
            r"anthropic\.Anthropic\(",
            r"client\.messages\.create",
            r"Anthropic\(\s*\)",
            r"AsyncAnthropic\(",
            # Java
            r"AnthropicChatModel\b",
        ],
        model_extraction=r"model\s*=\s*[\"']([^\"']+)[\"']",
        dep_names=["anthropic", "@anthropic-ai/sdk"],
    ),
    # 3. Google AI
    LLMPattern(
        sdk_name="Google AI",
        provider="Google",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"import\s+google\.generativeai",
            r"from\s+google\.generativeai",
            r"from\s+vertexai",
            r"import\s+vertexai",
        ],
        usage_patterns=[
            r"genai\.GenerativeModel\(",
            r"GenerativeModel\(",
            r"vertexai\.init\(",
        ],
        model_extraction=r"GenerativeModel\([\"']([^\"']+)[\"']",
        dep_names=["google-generativeai", "vertexai", "google-cloud-aiplatform"],
    ),
    # 4. LangChain (Python + JavaScript/TypeScript)
    LLMPattern(
        sdk_name="LangChain",
        provider="LangChain",
        component_type=ComponentType.agent_framework,
        usage_type=UsageType.orchestration,
        import_patterns=[
            # Python
            r"from\s+langchain",
            r"import\s+langchain",
            r"from\s+langchain_core",
            r"from\s+langchain_openai",
            r"from\s+langchain_anthropic",
            r"from\s+langchain_community",
            r"from\s+langchain_google_genai",
            # JavaScript/TypeScript
            r"from\s+['\"]@langchain/",
            r"require\(['\"]@langchain/",
            r"from\s+['\"]langchain['\"]",
        ],
        usage_patterns=[
            r"ChatOpenAI\(",
            r"ChatAnthropic\(",
            r"LLMChain\(",
            r"ConversationChain\(",
            r"AgentExecutor\(",
            r"create_react_agent\(",
            r"PromptTemplate\(",
            r"ChatPromptTemplate\.",
            r"RetrievalQA\.",
            r"load_tools\(",
        ],
        model_extraction=r"model(?:_name)?\s*=\s*[\"']([^\"']+)[\"']",
        dep_names=[
            "langchain",
            "langchain-core",
            "langchain-openai",
            "langchain-anthropic",
            "langchain-community",
            "langchain-google-genai",
        ],
    ),
    # 5. LangGraph
    LLMPattern(
        sdk_name="LangGraph",
        provider="LangChain",
        component_type=ComponentType.agent_framework,
        usage_type=UsageType.orchestration,
        import_patterns=[
            r"from\s+langgraph",
            r"import\s+langgraph",
        ],
        usage_patterns=[
            r"StateGraph\(",
            r"MessageGraph\(",
            r"CompiledGraph",
        ],
        model_extraction=None,
        dep_names=["langgraph"],
    ),
    # 6. CrewAI
    LLMPattern(
        sdk_name="CrewAI",
        provider="CrewAI",
        component_type=ComponentType.agent_framework,
        usage_type=UsageType.agent,
        import_patterns=[
            r"from\s+crewai\s+import",
            r"import\s+crewai",
            r"from\s+crewai\.flow",
        ],
        usage_patterns=[
            r"Agent\(",
            r"Task\(",
            r"Crew\(",
            r"crew\.kickoff\(",
            # CrewAI flow decorators
            r"@crew\b",
            r"@agent\b",
            r"@task\b",
            r"@flow\b",
            r"@tool\b",
            r"@start\b",
            r"@listen\b",
            r"@router\b",
        ],
        model_extraction=None,
        dep_names=["crewai"],
    ),
    # 7. AutoGen
    LLMPattern(
        sdk_name="AutoGen",
        provider="Microsoft",
        component_type=ComponentType.agent_framework,
        usage_type=UsageType.agent,
        import_patterns=[
            r"from\s+autogen\s+import",
            r"import\s+autogen",
            r"from\s+pyautogen",
        ],
        usage_patterns=[
            r"AssistantAgent\(",
            r"UserProxyAgent\(",
            r"GroupChat\(",
            r"GroupChatManager\(",
        ],
        model_extraction=None,
        dep_names=["autogen", "pyautogen"],
    ),
    # 8. LlamaIndex
    LLMPattern(
        sdk_name="LlamaIndex",
        provider="LlamaIndex",
        component_type=ComponentType.agent_framework,
        usage_type=UsageType.orchestration,
        import_patterns=[
            r"from\s+llama_index",
            r"import\s+llama_index",
        ],
        usage_patterns=[
            r"VectorStoreIndex\(",
            r"SimpleDirectoryReader\(",
            r"ServiceContext\.",
            r"StorageContext\.",
        ],
        model_extraction=None,
        dep_names=["llama-index", "llama_index"],
    ),
    # 9. HuggingFace Transformers
    LLMPattern(
        sdk_name="HuggingFace Transformers",
        provider="HuggingFace",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"from\s+transformers\s+import",
            r"import\s+transformers",
        ],
        usage_patterns=[
            r"AutoModel\.",
            r"AutoTokenizer\.",
            r"pipeline\(",
            r"Trainer\(",
            r"from_pretrained\(",
        ],
        model_extraction=r"from_pretrained\([\"']([^\"']+)[\"']",
        dep_names=["transformers", "huggingface-hub"],
    ),
    # 10. Ollama
    LLMPattern(
        sdk_name="Ollama",
        provider="Ollama",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"import\s+ollama",
            r"from\s+ollama",
        ],
        usage_patterns=[
            r"ollama\.chat\(",
            r"ollama\.generate\(",
            r"ollama\.embeddings\(",
        ],
        model_extraction=r"model\s*=\s*[\"']([^\"']+)[\"']",
        dep_names=["ollama"],
    ),
    # 11. Cohere
    LLMPattern(
        sdk_name="Cohere",
        provider="Cohere",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"import\s+cohere",
            r"from\s+cohere",
        ],
        usage_patterns=[
            r"cohere\.Client\(",
            r"co\.chat\(",
            r"co\.generate\(",
            r"co\.embed\(",
        ],
        model_extraction=None,
        dep_names=["cohere"],
    ),
    # 12. Mistral
    LLMPattern(
        sdk_name="Mistral",
        provider="Mistral",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"from\s+mistralai",
            r"import\s+mistralai",
        ],
        usage_patterns=[
            r"MistralClient\(",
            r"Mistral\(",
            r"client\.chat\(",
        ],
        model_extraction=None,
        dep_names=["mistralai"],
    ),
    # 13. AWS Bedrock
    LLMPattern(
        sdk_name="AWS Bedrock",
        provider="AWS Bedrock",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"import\s+boto3",
        ],
        usage_patterns=[
            r"bedrock-runtime",
            r"invoke_model\(",
            r"bedrock\.invoke_model",
            r"BedrockRuntime",
        ],
        model_extraction=r"modelId\s*=\s*[\"']([^\"']+)[\"']",
        dep_names=["boto3"],
    ),
    # 14. Azure OpenAI
    LLMPattern(
        sdk_name="Azure OpenAI",
        provider="Azure OpenAI",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"from\s+openai\s+import\s+AzureOpenAI",
            r"AzureOpenAI\(",
        ],
        usage_patterns=[
            r"AzureOpenAI\(",
            r"azure_endpoint\s*=",
        ],
        model_extraction=None,
        dep_names=["openai"],
    ),
    # 15. Replicate
    LLMPattern(
        sdk_name="Replicate",
        provider="Replicate",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"import\s+replicate",
            r"from\s+replicate",
        ],
        usage_patterns=[
            r"replicate\.run\(",
            r"replicate\.predictions\.create\(",
        ],
        model_extraction=None,
        dep_names=["replicate"],
    ),
    # 16. Together AI
    LLMPattern(
        sdk_name="Together AI",
        provider="Together",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"import\s+together",
            r"from\s+together",
        ],
        usage_patterns=[
            r"Together\(",
            r"together\.chat\.completions",
        ],
        model_extraction=None,
        dep_names=["together"],
    ),
    # 17. vLLM
    LLMPattern(
        sdk_name="vLLM",
        provider="vLLM",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"from\s+vllm\s+import",
            r"import\s+vllm",
        ],
        usage_patterns=[
            r"LLM\(",
            r"SamplingParams\(",
        ],
        model_extraction=None,
        dep_names=["vllm"],
    ),
    # 18. MCP (Model Context Protocol)
    LLMPattern(
        sdk_name="MCP",
        provider="Anthropic",
        component_type=ComponentType.tool,
        usage_type=UsageType.tool_use,
        import_patterns=[
            r"from\s+mcp\s+import",
            r"import\s+mcp",
            r"from\s+mcp\.server",
            r"from\s+mcp\.client",
        ],
        usage_patterns=[
            r"MCPServer\(",
            r"MCPClient\(",
            r"@mcp\.tool",
            r"mcp\.run\(",
        ],
        model_extraction=None,
        dep_names=["mcp"],
    ),
    # 19. DSPy
    LLMPattern(
        sdk_name="DSPy",
        provider="Stanford",
        component_type=ComponentType.agent_framework,
        usage_type=UsageType.orchestration,
        import_patterns=[
            r"import\s+dspy",
            r"from\s+dspy",
        ],
        usage_patterns=[
            r"dspy\.OpenAI\(",
            r"dspy\.Predict\(",
            r"dspy\.ChainOfThought\(",
            r"dspy\.Module",
        ],
        model_extraction=None,
        dep_names=["dspy", "dspy-ai"],
    ),
    # 20. Semantic Kernel
    LLMPattern(
        sdk_name="Semantic Kernel",
        provider="Microsoft",
        component_type=ComponentType.agent_framework,
        usage_type=UsageType.orchestration,
        import_patterns=[
            r"from\s+semantic_kernel",
            r"import\s+semantic_kernel",
        ],
        usage_patterns=[
            r"Kernel\(",
            r"kernel\.add_plugin",
            r"kernel\.invoke",
        ],
        model_extraction=None,
        dep_names=["semantic-kernel"],
    ),
    # 21. LiteLLM
    LLMPattern(
        sdk_name="LiteLLM",
        provider="LiteLLM",
        component_type=ComponentType.llm_provider,
        usage_type=UsageType.completion,
        import_patterns=[
            r"from\s+litellm",
            r"import\s+litellm",
        ],
        usage_patterns=[
            r"litellm\.completion\(",
            r"litellm\.acompletion\(",
        ],
        model_extraction=None,
        dep_names=["litellm"],
    ),
    # 22. LangChain4j (Java)
    LLMPattern(
        sdk_name="LangChain4j",
        provider="LangChain4j",
        component_type=ComponentType.agent_framework,
        usage_type=UsageType.orchestration,
        import_patterns=[
            r"import\s+dev\.langchain4j",
        ],
        usage_patterns=[
            r"OpenAiChatModel\.builder\(",
            r"AnthropicChatModel\.builder\(",
            r"ChatLanguageModel\b",
        ],
        model_extraction=r"modelName\([\"']([^\"']+)[\"']\)",
        dep_names=["dev.langchain4j"],
    ),
]


def get_all_dep_names() -> set[str]:
    """
    Return all known AI package/dependency names across all patterns.

    This is useful for filtering dependency files and identifying potential
    AI-related packages even without code scanning.

    Returns:
        Set of all package names from dep_names across all LLM patterns
    """
    names: set[str] = set()
    for pattern in LLM_PATTERNS:
        names.update(pattern.dep_names)
    return names
