import type {
  IWebhookFunctions,
  IWebhookResponseData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';

export class TruseraWebhook implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Webhook',
    name: 'truseraWebhook',
    icon: 'file:trusera.svg',
    group: ['trigger'],
    version: 1,
    subtitle: 'AI Security Trigger',
    description:
      'Pre-configured webhook trigger for the Trusera AI-BOM dashboard. Connect to a Trusera Dashboard node for a one-click security dashboard.',
    defaults: {
      name: 'Trusera Webhook',
    },
    inputs: [],
    outputs: ['main'],
    webhooks: [
      {
        name: 'default',
        httpMethod: 'GET',
        responseMode: 'lastNode',
        path: 'trusera',
      },
    ],
    properties: [],
  };

  async webhook(this: IWebhookFunctions): Promise<IWebhookResponseData> {
    const req = this.getRequestObject();
    return {
      workflowData: [
        [
          {
            json: {
              headers: req.headers as Record<string, unknown>,
              params: req.query as Record<string, unknown>,
              timestamp: new Date().toISOString(),
            },
          },
        ],
      ],
    };
  }
}
