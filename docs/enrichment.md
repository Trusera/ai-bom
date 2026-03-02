# LLM Enrichment

AI-BOM can optionally use an LLM to analyze code snippets around detected AI components and extract the specific model names being used (e.g., `gpt-4o`, `claude-3-opus-20240229`, `llama3`).

This fills the `model_name` field that static pattern matching may leave empty, particularly when model names are passed as variables or constructed dynamically.

---

## Installation

LLM enrichment requires the `litellm` package:

```bash
pip install ai-bom[enrich]
```

---

## Usage

### Basic

```bash
ai-bom scan . --llm-enrich
```

This uses `gpt-4o-mini` by default (requires `OPENAI_API_KEY` environment variable).

### With a specific model

```bash
# OpenAI
ai-bom scan . --llm-enrich --llm-model gpt-4o

# Anthropic
ai-bom scan . --llm-enrich --llm-model anthropic/claude-3-haiku-20240307

# Local Ollama (no API key needed)
ai-bom scan . --llm-enrich --llm-model ollama/llama3 --llm-base-url http://localhost:11434
```

### With an explicit API key

```bash
ai-bom scan . --llm-enrich --llm-api-key sk-your-key-here
```

If `--llm-api-key` is not provided, litellm falls back to standard environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.).

---

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--llm-enrich` | `False` | Enable LLM enrichment |
| `--llm-model` | `gpt-4o-mini` | litellm model identifier |
| `--llm-api-key` | None | API key (falls back to env vars) |
| `--llm-base-url` | None | Custom API base URL (e.g., Ollama) |

---

## How It Works

1. After all scanners run, components with type `llm_provider` or `model` that have an empty `model_name` are selected for enrichment.
2. For each eligible component, ~20 lines of code around the detection site are read from the source file.
3. The code snippet is sent to the configured LLM with a prompt asking it to extract the model identifier.
4. The response is parsed and cross-referenced with AI-BOM's built-in model registry to validate the name and fill in provider/deprecation metadata.
5. If the LLM call fails or returns no model name, the component is left unchanged.

Components that already have a `model_name` (from static detection) are skipped. Non-model component types (containers, tools, MCP servers, workflows) are never sent to the LLM.

---

## Privacy and Security

**Code snippets are sent to the LLM provider.** When using cloud-hosted models (OpenAI, Anthropic, etc.), approximately 20 lines of source code around each detected AI import or usage site are transmitted to the provider's API.

Recommendations:

- **For sensitive or proprietary codebases**, use a local model via Ollama (`--llm-model ollama/llama3`). No data leaves your machine.
- **Before using cloud APIs**, ensure you have organizational approval to send source code excerpts to the provider.
- **Only code around detected AI components** is sent — not entire files, not the full repository.
- AI-BOM does not intentionally include secrets in snippets, but if API keys are hard-coded near import statements, they may be included in the context window. Use `--deep` scanning to detect and remediate hard-coded keys separately.

A warning is printed when using non-local models:

```
Warning: LLM enrichment sends code snippets to an external API.
Use ollama/* models for local-only processing.
```

---

## Cost

Each eligible component triggers one or more LLM API calls. For projects with many detected AI components, this can result in non-trivial API costs when using paid providers.

- Components are batched (default: 5 per call) to reduce the number of API requests.
- Use a low-cost model like `gpt-4o-mini` for bulk enrichment.
- **Ollama is free** — run models locally with zero API cost.

---

## Supported Providers

LLM enrichment uses [litellm](https://docs.litellm.ai/) as its backend, which supports 100+ LLM providers including:

- OpenAI (`gpt-4o`, `gpt-4o-mini`, etc.)
- Anthropic (`anthropic/claude-3-haiku-20240307`, etc.)
- Ollama (`ollama/llama3`, `ollama/mistral`, etc.)
- Azure OpenAI, AWS Bedrock, Google Vertex AI
- Mistral, Cohere, and many more

See the [litellm provider list](https://docs.litellm.ai/docs/providers) for the full list.
