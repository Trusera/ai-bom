import type {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';


import { scanWorkflows } from '../../lib/scanner';
import { generateDashboardHtml } from '../../lib/dashboardHtml';

export class TruseraDashboard implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Dashboard',
    name: 'truseraDashboard',
    icon: 'file:trusera.png',
    group: ['output'],
    version: 1,
    subtitle: 'AI Security Dashboard',
    description:
      'Fetch all n8n workflows, scan them for AI security risks, and return an interactive HTML dashboard',
    defaults: {
      name: 'Trusera Dashboard',
    },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'truseraApi',
        required: true,
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

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const creds = await this.getCredentials('truseraApi');
    const baseUrl = (creds.baseUrl as string).replace(/\/$/, '');
    const password = this.getNodeParameter('password', 0, '') as string;

    // Fetch all workflows via n8n REST API (paginated)
    const allWorkflows: Array<Record<string, unknown>> = [];
    let cursor: string | null = null;
    do {
      const url =
        `${baseUrl}/api/v1/workflows?limit=100` +
        (cursor ? `&cursor=${cursor}` : '');
      const resp = await this.helpers.httpRequestWithAuthentication.call(
        this,
        'truseraApi',
        { method: 'GET', url, json: true },
      );
      const data = resp as { data: Array<Record<string, unknown>>; nextCursor?: string };
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

    return [[{
      json: {
        html,
        headers: { 'content-type': 'text/html; charset=utf-8' },
        statusCode: 200,
        body: html,
      },
    }]];
  }
}
