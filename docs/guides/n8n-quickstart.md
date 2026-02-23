# n8n + AI-BOM Integration Quickstart

Scan your n8n workflows for AI security risks and generate an AI Bill of Materials (AI-BOM) directly within your automation.

## 1. Install the Community Node
1. Open your n8n instance.
2. Go to **Settings > Community Nodes**.
3. Click **Install a community node**.
4. Enter `n8n-nodes-trusera` and click **Install**.

## 2. Create a Security Scan Workflow
A common patterns is to scan workflows and notify security teams of critical risks.

**Workflow Logic:**
`HTTP Trigger` → `AI Agent Node` → `Trusera Scan` → `Slack Notification`

### Steps:
1. **HTTP Trigger:** Set up a webhook to trigger the scan (e.g., after a deployment).
2. **AI Agent:** Your existing agent logic you wish to monitor.
3. **Trusera Scan:** - Add the **Trusera Scan** node.
   - Configure your **n8n API Key** in the node credentials.
   - Set the scan target to your workflow ID.
4. **Slack:** Filter for `risk_score > 70` and send an alert to your security channel.

## 3. Cross-linking
For full documentation on risk scores and CycloneDX output formats, refer to the [Main README](../../README.md).