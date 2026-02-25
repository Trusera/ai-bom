# AI-BOM Tool Comparison

This document compares **ai-bom** with other AI Bill of Materials tools currently available in the ecosystem.

The goal is to help users understand feature differences and choose the right tool for their workflow.

---

## Feature Comparison

| Feature | ai-bom | Cisco AIBOM | Snyk AIBOM |
|--------|--------|-------------|-----------|
| License | Apache 2.0 | Apache 2.0 | Proprietary |
| Open Source | Yes | Yes | No |
| Scanners | 13+ (code, cloud, Docker, GitHub Actions, Jupyter, MCP, n8n, etc.) | 1 (Python-focused) | Unknown |
| Output Formats | 9 (Table, JSON, SARIF, SPDX, CycloneDX, CSV, HTML, Markdown, JUnit) | JSON, CSV | Unknown |
| CI/CD Integration | GitHub Action, GitLab CI | No | Yes |
| LLM Enrichment | No | Yes | Early access / limited preview |
| n8n Scanning | Yes | No | No |
| MCP / A2A Detection | Yes | No | No |
| Agent Framework Detection | LangChain, CrewAI, AutoGen, LlamaIndex, Semantic Kernel | Limited | Unknown |
| Binary Model Detection | Yes (.onnx, .pt, .safetensors, etc.) | No | Unknown |
| Policy Enforcement | Cedar policy gate | No | Yes |
| Best For | Multi-framework projects needing multiple formats | Python projects needing LLM enrichment | Existing Snyk customers |

---

## Notes

### ai-bom

- Open-source AI Bill of Materials scanner focused on discovering AI/LLM usage across codebases and infrastructure.
- Supports multiple scanners, formats, and compliance mappings (OWASP Agentic Top 10, EU AI Act).
- Designed for developer workflows with CLI, CI/CD, and dashboard support.

### Cisco AIBOM

- Open-source tool focused primarily on Python projects.
- Uses LLM-based enrichment to extract model usage.
- Limited scanner coverage and output formats compared to ai-bom.

### Snyk AIBOM

- Proprietary feature integrated into the Snyk platform.
- Currently in early access / limited preview.
- Provides CI/CD integration.
- Public documentation on supported scanners and formats is limited.

---

_Last updated: 2026_