# GitHub Actions: AI-BOM on Pull Requests

This guide shows how to run AI-BOM on every pull request to detect AI/ML supply chain risks in CI.

## What it does

On every PR:
- Runs `ai-bom scan`
- Uploads an AIBOM JSON artifact
- Posts a PR comment with PASS/FAIL, component count, and risk score

## Setup

1. Copy the workflow file:

   `.github/workflows/ai-bom-scan.yml`

2. Open a pull request — the workflow runs automatically.

## Configuration

You can modify these values inside the workflow:

- `RISK_THRESHOLD` (default: 70)
- `ENFORCE_GATE` (default: false)

If `ENFORCE_GATE` is set to `true`, the workflow will fail when the scan result is FAIL.

## Output

Each run produces:

- `aibom.json` (AI-BOM JSON artifact)
- `aibom-summary.json` (summary used for PR comment)

The PR comment includes:

- PASS / FAIL status
- Components found
- Risk score
- Risky component count