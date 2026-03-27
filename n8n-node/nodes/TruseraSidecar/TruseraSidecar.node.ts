import type {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';

import { SidecarEvaluator } from '../../lib/sidecar/evaluator';
import { SidecarReporter } from '../../lib/sidecar/reporter';
import type { EnforcementMode, PolicySource } from '../../lib/sidecar/types';

export class TruseraSidecar implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Sidecar',
    name: 'truseraSidecar',
    icon: 'file:trusera.png',
    group: ['transform'],
    version: 1,
    subtitle: '={{$parameter["enforcementMode"]}} mode',
    description:
      'Runtime AI security guard — evaluates data against Cedar policies, detects PII, and blocks policy violations',
    defaults: {
      name: 'Trusera Sidecar',
    },
    inputs: ['main'],
    outputs: ['main', 'main'],
    outputNames: ['Pass', 'Block'],
    credentials: [
      {
        name: 'truseraPlatformApi',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Agent Name',
        name: 'agentName',
        type: 'string',
        default: '',
        required: true,
        description: 'Name for this agent in the Trusera platform (used for registration and event tracking)',
      },
      {
        displayName: 'Enforcement Mode',
        name: 'enforcementMode',
        type: 'options',
        options: [
          { name: 'Log Only', value: 'log', description: 'Record events but never interfere' },
          { name: 'Warn', value: 'warn', description: 'Log warnings and pass data through' },
          { name: 'Block', value: 'block', description: 'Route violations to Block output' },
        ],
        default: 'warn',
        description: 'What happens when a policy violation is detected',
      },
      {
        displayName: 'Policy Source',
        name: 'policySource',
        type: 'options',
        options: [
          {
            name: 'Platform Policies',
            value: 'platform',
            description: 'Fetch Cedar policies from the Trusera platform',
          },
          {
            name: 'Inline Policy',
            value: 'inline',
            description: 'Write Cedar DSL directly in this node',
          },
        ],
        default: 'platform',
        description: 'Where to load Cedar policies from',
      },
      {
        displayName: 'Cedar Policy DSL',
        name: 'inlineCedarDsl',
        type: 'string',
        typeOptions: { rows: 8 },
        default: '',
        displayOptions: {
          show: {
            policySource: ['inline'],
          },
        },
        description:
          'Cedar policy DSL to evaluate. Example: forbid (principal, action == Action::"*", resource) when { resource.pii_detected == "true" };',
      },
      {
        displayName: 'Enable PII Detection',
        name: 'enablePiiDetection',
        type: 'boolean',
        default: true,
        description: 'Whether to scan data for personally identifiable information (SSN, credit cards, emails, etc.)',
      },
      {
        displayName: 'Enable Prompt Injection Detection',
        name: 'enablePromptInjection',
        type: 'boolean',
        default: true,
        description: 'Whether to detect prompt injection patterns in text data',
      },
      {
        displayName: 'Enable Content Filter',
        name: 'enableContentFilter',
        type: 'boolean',
        default: false,
        description: 'Whether to check for dangerous content patterns (SQL injection, shell injection, path traversal)',
      },
      {
        displayName: 'Data Field',
        name: 'dataField',
        type: 'string',
        default: '',
        description:
          'Specific JSON field to evaluate. Leave empty to evaluate the entire input.',
      },
      {
        displayName: 'Policy Cache TTL (Seconds)',
        name: 'policyCacheTtl',
        type: 'number',
        default: 60,
        description: 'How long to cache policies from the platform (0 = no cache)',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const passData: INodeExecutionData[] = [];
    const blockData: INodeExecutionData[] = [];

    const credentials = (await this.getCredentials('truseraPlatformApi')) as {
      apiKey: string;
      platformUrl: string;
    };

    const agentName = this.getNodeParameter('agentName', 0, '') as string;
    const enforcementMode = this.getNodeParameter('enforcementMode', 0, 'warn') as EnforcementMode;
    const policySource = this.getNodeParameter('policySource', 0, 'platform') as PolicySource;
    const inlineCedarDsl = this.getNodeParameter('inlineCedarDsl', 0, '') as string;
    const enablePiiDetection = this.getNodeParameter('enablePiiDetection', 0, true) as boolean;
    const enablePromptInjection = this.getNodeParameter('enablePromptInjection', 0, true) as boolean;
    const enableContentFilter = this.getNodeParameter('enableContentFilter', 0, false) as boolean;
    const dataField = this.getNodeParameter('dataField', 0, '') as string;
    const policyCacheTtl = this.getNodeParameter('policyCacheTtl', 0, 60) as number;

    const evaluator = new SidecarEvaluator({
      platformUrl: credentials.platformUrl,
      apiKey: credentials.apiKey,
      enforcementMode,
      policySource,
      agentName,
      enablePiiDetection,
      enablePromptInjection,
      enableContentFilter,
      inlineCedarDsl,
      policyCacheTtlMs: policyCacheTtl * 1000,
    });

    const reporter = new SidecarReporter(
      credentials.platformUrl,
      credentials.apiKey,
      agentName,
    );

    for (let i = 0; i < items.length; i++) {
      const inputJson = items[i].json;

      // Extract the data to evaluate
      const dataToEvaluate: Record<string, unknown> = dataField
        ? ({ [dataField]: inputJson[dataField] } as Record<string, unknown>)
        : (inputJson as Record<string, unknown>);

      // Skip evaluation if no data
      if (!dataToEvaluate || Object.keys(dataToEvaluate).length === 0) {
        passData.push(items[i]);
        continue;
      }

      const result = await evaluator.evaluate(dataToEvaluate);

      // Track event
      reporter.track(
        reporter.createEvaluationEvent(result, dataToEvaluate, 'TruseraSidecar'),
      );

      const truseraMetadata = {
        decision: result.allowed ? 'allow' : 'deny',
        enforcement: result.enforcement,
        violations: result.violations,
        checks: result.checks.map((c) => ({
          name: c.name,
          passed: c.passed,
          ...(c.findings?.length ? { findings: c.findings } : {}),
        })),
        durationMs: result.durationMs,
        timestamp: result.timestamp,
      };

      if (result.violations.length === 0 || enforcementMode !== 'block') {
        // Pass through — enrich with metadata
        passData.push({
          json: {
            ...inputJson,
            _trusera: truseraMetadata,
          },
          pairedItem: { item: i },
        });

        if (result.violations.length > 0 && enforcementMode === 'warn') {
          console.warn(
            `[Trusera Sidecar] Policy violation (warn mode): ${result.violations.map((v) => v.reason).join('; ')}`,
          );
        }
      } else {
        // Block — route to second output
        blockData.push({
          json: {
            ...inputJson,
            _trusera: truseraMetadata,
          },
          pairedItem: { item: i },
        });
      }
    }

    // Flush events (fire-and-forget)
    try {
      await reporter.flush();
    } catch {
      // Event reporting failure is non-fatal
    }

    return [passData, blockData];
  }
}
