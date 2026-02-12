import type {
  IWebhookFunctions,
  IWebhookResponseData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';

import { scanWorkflows } from '../../lib/scanner';
import { generateDashboardHtml } from '../../lib/dashboardHtml';

export class TruseraWebhook implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Webhook',
    name: 'truseraWebhook',
    icon: 'file:trusera.svg',
    group: ['trigger'],
    version: 1,
    subtitle: 'AI Security Dashboard',
    description:
      'One-node security dashboard — add n8n API credentials, activate, and visit /webhook/trusera to see your AI-BOM report.',
    defaults: {
      name: 'Trusera Webhook',
      webhookId: 'trusera-ai-bom',
    } as INodeTypeDescription['defaults'],
    inputs: [],
    outputs: ['main'],
    credentials: [
      {
        name: 'truseraApi',
        required: true,
      },
    ],
    webhooks: [
      {
        name: 'default',
        httpMethod: 'GET',
        responseMode: 'lastNode',
        path: 'trusera',
        isFullPath: true,
      },
    ],
    properties: [
      {
        displayName: 'Dashboard Password',
        name: 'password',
        type: 'string',
        typeOptions: { password: true },
        default: '',
        description:
          'Optional. If set, the dashboard is AES-256-GCM encrypted and visitors must enter this password to view it.',
      },
    ],
  };

  async webhook(this: IWebhookFunctions): Promise<IWebhookResponseData> {
    const res = this.getResponseObject();

    try {
      const creds = await this.getCredentials('truseraApi');
      const baseUrl = ((creds.baseUrl as string) || 'http://localhost:5678').replace(/\/$/, '');
      const apiKey = creds.apiKey as string;
      const password = this.getNodeParameter('password', '') as string;

      // Fetch all workflows via n8n REST API (paginated)
      const allWorkflows: Array<Record<string, unknown>> = [];
      let cursor: string | null = null;
      do {
        const url =
          `${baseUrl}/api/v1/workflows?limit=100` +
          (cursor ? `&cursor=${cursor}` : '');
        const resp = await fetch(url, {
          headers: {
            'X-N8N-API-KEY': apiKey,
            'Accept': 'application/json',
          },
        });
        if (!resp.ok) {
          throw new Error(`n8n API error: ${resp.status} ${await resp.text()}`);
        }
        const data = (await resp.json()) as {
          data: Array<Record<string, unknown>>;
          nextCursor?: string;
        };
        allWorkflows.push(...data.data);
        cursor = data.nextCursor ?? null;
      } while (cursor);

      // Scan all workflows
      const workflows = allWorkflows.map((wf) => ({
        data: wf,
        filePath: (wf.name as string) || (wf.id as string) || 'unknown',
      }));
      const scanResult = scanWorkflows(workflows);

      // Generate HTML dashboard
      const html = generateDashboardHtml(scanResult, password || undefined);

      // Serve HTML directly
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.status(200).end(html);
    } catch (err) {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.status(500).end(
        `<!DOCTYPE html><html><body style="font-family:sans-serif;padding:40px">` +
        `<h1>Trusera Dashboard Error</h1>` +
        `<pre style="color:red">${(err as Error).message}</pre>` +
        `</body></html>`,
      );
    }

    return {
      noWebhookResponse: true,
      workflowData: [
        [{ json: { served: true, timestamp: new Date().toISOString() } }],
      ],
    };
  }
}
