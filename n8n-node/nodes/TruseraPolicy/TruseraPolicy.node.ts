import type {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';

import { evaluatePolicy, Policy } from '../../lib/policyEngine';
import type { ScanResult } from '../../lib/models';

export class TruseraPolicy implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Policy',
    name: 'truseraPolicy',
    icon: 'file:trusera.png',
    group: ['transform'],
    version: 1,
    subtitle: 'Enforce AI security policy',
    description: 'Evaluate AI-BOM scan results against a security policy',
    defaults: {
      name: 'Trusera Policy',
    },
    inputs: ['main'],
    outputs: ['main'],
    properties: [
      {
        displayName: 'Scan Result Field',
        name: 'scanResultField',
        type: 'string',
        default: '',
        description:
          'Field containing the scan result. If empty, the entire input JSON is used.',
      },
      {
        displayName: 'Max Critical',
        name: 'maxCritical',
        type: 'number',
        default: 0,
        description: 'Maximum number of critical-severity components allowed',
      },
      {
        displayName: 'Max High',
        name: 'maxHigh',
        type: 'number',
        default: -1,
        description:
          'Maximum number of high-severity components allowed (-1 = unlimited)',
      },
      {
        displayName: 'Max Risk Score',
        name: 'maxRiskScore',
        type: 'number',
        default: -1,
        description:
          'Maximum risk score allowed for any component (-1 = unlimited)',
      },
      {
        displayName: 'Block Providers',
        name: 'blockProviders',
        type: 'string',
        default: '',
        description:
          'Comma-separated list of AI providers to block (e.g. "OpenAI,Anthropic")',
      },
      {
        displayName: 'Block Flags',
        name: 'blockFlags',
        type: 'string',
        default: '',
        description:
          'Comma-separated list of risk flags to block (e.g. "hardcoded_api_key,no_auth")',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      const scanResultField = this.getNodeParameter('scanResultField', i, '') as string;
      const maxCritical = this.getNodeParameter('maxCritical', i, 0) as number;
      const maxHigh = this.getNodeParameter('maxHigh', i, -1) as number;
      const maxRiskScore = this.getNodeParameter('maxRiskScore', i, -1) as number;
      const blockProvidersStr = this.getNodeParameter('blockProviders', i, '') as string;
      const blockFlagsStr = this.getNodeParameter('blockFlags', i, '') as string;

      const scanResult: ScanResult = scanResultField
        ? (items[i].json[scanResultField] as unknown as ScanResult)
        : (items[i].json as unknown as ScanResult);

      if (!scanResult || !Array.isArray(scanResult.components)) {
        returnData.push({
          json: {
            passed: false,
            violations: ['Invalid scan result: missing components array'],
          },
        });
        continue;
      }

      const policy: Policy = {
        maxCritical,
        blockProviders: blockProvidersStr
          ? blockProvidersStr.split(',').map((s) => s.trim())
          : [],
        blockFlags: blockFlagsStr
          ? blockFlagsStr.split(',').map((s) => s.trim())
          : [],
      };

      if (maxHigh >= 0) policy.maxHigh = maxHigh;
      if (maxRiskScore >= 0) policy.maxRiskScore = maxRiskScore;

      const result = evaluatePolicy(scanResult, policy);

      returnData.push({
        json: {
          ...result,
          policyApplied: policy,
          totalComponents: scanResult.components.length,
        },
      });
    }

    return [returnData];
  }
}
