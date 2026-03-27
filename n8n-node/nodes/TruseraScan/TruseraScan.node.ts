import type {
  IDataObject,
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';

import { scanWorkflow, scanWorkflows, isValidWorkflow } from '../../lib/scanner';

export class TruseraScan implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Scan',
    name: 'truseraScan',
    icon: 'file:trusera.png',
    group: ['transform'],
    version: 1,
    subtitle: '={{$parameter["operation"]}}',
    description: 'Scan n8n workflows for AI security risks using Trusera AI-BOM',
    defaults: {
      name: 'Trusera Scan',
    },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'truseraApi',
        required: false,
      },
    ],
    properties: [
      {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        noDataExpression: true,
        options: [
          {
            name: 'Scan Workflow JSON',
            value: 'scanJson',
            description: 'Scan a workflow JSON object from input',
            action: 'Scan a workflow JSON object',
          },
          {
            name: 'Scan Multiple Workflows',
            value: 'scanMultiple',
            description: 'Scan multiple workflow JSON objects from input array',
            action: 'Scan multiple workflow JSON objects',
          },
        ],
        default: 'scanJson',
      },
      {
        displayName: 'Workflow JSON Field',
        name: 'jsonField',
        type: 'string',
        default: 'json',
        required: true,
        description: 'Name of the input field containing the n8n workflow JSON',
        displayOptions: {
          show: {
            operation: ['scanJson'],
          },
        },
      },
      {
        displayName: 'Workflows Array Field',
        name: 'arrayField',
        type: 'string',
        default: 'workflows',
        required: true,
        description: 'Name of the input field containing an array of workflow JSON objects',
        displayOptions: {
          show: {
            operation: ['scanMultiple'],
          },
        },
      },
      {
        displayName: 'File Path',
        name: 'filePath',
        type: 'string',
        default: 'workflow.json',
        required: false,
        description: 'Virtual file path used in scan results for identification',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      const operation = this.getNodeParameter('operation', i) as string;
      const filePath = this.getNodeParameter('filePath', i, 'workflow.json') as string;

      if (operation === 'scanJson') {
        const jsonField = this.getNodeParameter('jsonField', i) as string;
        const workflowData = items[i].json[jsonField] ?? items[i].json;

        if (!isValidWorkflow(workflowData)) {
          returnData.push({
            json: {
              error: 'Invalid n8n workflow JSON: missing nodes or connections',
              components: [],
              summary: null,
            },
          });
          continue;
        }

        const components = scanWorkflow(workflowData, filePath);
        returnData.push({
          json: {
            components,
            totalComponents: components.length,
            filePath,
          },
        });
      } else if (operation === 'scanMultiple') {
        const arrayField = this.getNodeParameter('arrayField', i) as string;
        const workflowsArray = items[i].json[arrayField];

        if (!Array.isArray(workflowsArray)) {
          returnData.push({
            json: {
              error: `Field "${arrayField}" is not an array`,
              components: [],
              summary: null,
            },
          });
          continue;
        }

        const workflows = workflowsArray.map((data: unknown, idx: number) => ({
          data,
          filePath: `${filePath.replace('.json', '')}_${idx}.json`,
        }));

        const result = scanWorkflows(workflows);
        returnData.push({
          json: result as unknown as IDataObject,
        });
      }
    }

    return [returnData];
  }
}
