import type {
  IAuthenticateGeneric,
  ICredentialTestRequest,
  ICredentialType,
  INodeProperties,
} from 'n8n-workflow';

export class TruseraPlatformApi implements ICredentialType {
  name = 'truseraPlatformApi';
  displayName = 'Trusera Platform API';
  documentationUrl = 'https://docs.trusera.dev/n8n-sidecar';

  properties: INodeProperties[] = [
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      required: true,
      description: 'Trusera platform API key (starts with tsk_)',
    },
    {
      displayName: 'Platform URL',
      name: 'platformUrl',
      type: 'string',
      default: 'https://api.trusera.io',
      required: false,
      description: 'Trusera platform API URL',
    },
  ];

  authenticate: IAuthenticateGeneric = {
    type: 'generic',
    properties: {
      headers: {
        Authorization: '=Bearer {{$credentials.apiKey}}',
      },
    },
  };

  test: ICredentialTestRequest = {
    request: {
      baseURL: '={{$credentials.platformUrl}}',
      url: '/api/v1/agents/stats',
      method: 'GET',
    },
  };
}
