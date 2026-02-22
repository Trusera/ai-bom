# GitHub Actions: AI-BOM on Pull Requests

This guide explains how to run **AI-BOM** on every pull request to detect AI/ML supply chain risks in CI.

The workflow uses the official GitHub Action:

`trusera/ai-bom@v1`

---

## What the Workflow Does

On every `pull_request` event:

- Runs `ai-bom scan` using the official GitHub Action
- Generates an **AIBOM JSON file** (`aibom.json`)
- Enforces a native policy gate using `fail-on: high`
- Uploads scan results as workflow artifacts
- Posts a PR comment with PASS/FAIL status and component count

---

## Setup

1. Copy the workflow file into your repository:

   `.github/workflows/ai-bom-scan.yml`

2. Ensure your repository includes dependency files such as:

   - `requirements.txt`
   - `pyproject.toml`

3. Open a pull request — the workflow runs automatically.

---

## Policy Gate (Native Enforcement)

The workflow uses the built-in AI-BOM policy gate:

```
fail-on: high
```

If high-risk components are detected:

- The PR comment will show **FAIL**
- The workflow will fail after posting the comment
- Artifacts are still uploaded for review

You can modify the `fail-on` level inside the workflow if needed (e.g., `medium`, `critical`).

---

## Workflow Outputs

Each run produces:

- `aibom.json` — full AI-BOM JSON output
- `aibom-summary.json` — summary used for PR comment

The PR comment includes:

- PASS / FAIL status
- Number of AI components detected
- Policy gate configuration

Artifacts can be downloaded from the workflow run page.
