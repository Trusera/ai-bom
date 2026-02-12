import type {
  IAuthenticateGeneric,
  ICredentialTestRequest,
  ICredentialType,
  INodeProperties,
} from 'n8n-workflow';

export class TruseraApi implements ICredentialType {
  name = 'truseraApi';
  displayName = 'n8n API';
  documentationUrl = 'https://docs.n8n.io/api/';

  properties: INodeProperties[] = [
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      required: true,
      description: 'n8n API key from Settings > n8n API',
    },
    {
      displayName: 'n8n Base URL',
      name: 'baseUrl',
      type: 'string',
      default: 'http://localhost:5678',
      required: false,
      description: 'URL of your n8n instance',
    },
  ];

  authenticate: IAuthenticateGeneric = {
    type: 'generic',
    properties: {
      headers: {
        'X-N8N-API-KEY': '={{$credentials.apiKey}}',
      },
    },
  };

  test: ICredentialTestRequest = {
    request: {
      baseURL: '={{$credentials.baseUrl}}',
      url: '/api/v1/workflows',
      method: 'GET',
    },
  };
}
