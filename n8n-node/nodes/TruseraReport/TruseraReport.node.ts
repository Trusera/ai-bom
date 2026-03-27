import type {
  IDataObject,
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';

import type { ScanResult, AIComponent } from '../../lib/models';
import { Severity } from '../../lib/models';
import { FLAG_DESCRIPTIONS } from '../../lib/riskScorer';

export class TruseraReport implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Trusera Report',
    name: 'truseraReport',
    icon: 'file:trusera.png',
    group: ['transform'],
    version: 1,
    subtitle: '={{$parameter["format"]}}',
    description: 'Generate a human-readable AI security report from scan results',
    defaults: {
      name: 'Trusera Report',
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
        displayName: 'Format',
        name: 'format',
        type: 'options',
        noDataExpression: true,
        options: [
          {
            name: 'Markdown',
            value: 'markdown',
            description: 'Generate a Markdown report',
            action: 'Generate Markdown report',
          },
          {
            name: 'JSON Summary',
            value: 'jsonSummary',
            description: 'Generate a compact JSON summary',
            action: 'Generate JSON summary',
          },
        ],
        default: 'markdown',
      },
      {
        displayName: 'Include Low Severity',
        name: 'includeLow',
        type: 'boolean',
        default: false,
        description: 'Whether to include low-severity findings in the report',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      const scanResultField = this.getNodeParameter('scanResultField', i, '') as string;
      const format = this.getNodeParameter('format', i) as string;
      const includeLow = this.getNodeParameter('includeLow', i, false) as boolean;

      const scanResult: ScanResult = scanResultField
        ? (items[i].json[scanResultField] as unknown as ScanResult)
        : (items[i].json as unknown as ScanResult);

      if (!scanResult || !Array.isArray(scanResult.components)) {
        returnData.push({
          json: { error: 'Invalid scan result: missing components array' },
        });
        continue;
      }

      const filtered = includeLow
        ? scanResult.components
        : scanResult.components.filter((c) => c.risk.severity !== Severity.Low);

      if (format === 'markdown') {
        returnData.push({
          json: { report: generateMarkdown(scanResult, filtered) },
        });
      } else {
        returnData.push({
          json: generateJsonSummary(scanResult, filtered) as unknown as IDataObject,
        });
      }
    }

    return [returnData];
  }
}

function severityEmoji(severity: string): string {
  switch (severity) {
    case 'critical': return '[CRITICAL]';
    case 'high': return '[HIGH]';
    case 'medium': return '[MEDIUM]';
    case 'low': return '[LOW]';
    default: return '';
  }
}

function generateMarkdown(result: ScanResult, components: AIComponent[]): string {
  const lines: string[] = [];

  lines.push('# Trusera AI-BOM Security Report');
  lines.push('');
  lines.push(`**Scan Date:** ${result.scanTimestamp}`);
  lines.push(`**Target:** ${result.targetPath}`);
  lines.push(`**AI-BOM Version:** ${result.aiBomVersion}`);
  lines.push('');

  // Summary
  const summary = result.summary;
  lines.push('## Summary');
  lines.push('');
  lines.push(`| Metric | Value |`);
  lines.push(`| --- | --- |`);
  lines.push(`| Total Components | ${summary.totalComponents} |`);
  lines.push(`| Files Scanned | ${summary.totalFilesScanned} |`);
  lines.push(`| Highest Risk Score | ${summary.highestRiskScore} |`);
  lines.push(`| Scan Duration | ${summary.scanDurationSeconds.toFixed(2)}s |`);
  lines.push('');

  // Severity breakdown
  if (Object.keys(summary.bySeverity).length > 0) {
    lines.push('### By Severity');
    lines.push('');
    for (const [sev, count] of Object.entries(summary.bySeverity)) {
      lines.push(`- ${severityEmoji(sev)} **${sev}**: ${count}`);
    }
    lines.push('');
  }

  // Provider breakdown
  if (Object.keys(summary.byProvider).length > 0) {
    lines.push('### By Provider');
    lines.push('');
    for (const [provider, count] of Object.entries(summary.byProvider)) {
      lines.push(`- **${provider}**: ${count}`);
    }
    lines.push('');
  }

  // Findings
  if (components.length > 0) {
    lines.push('## Findings');
    lines.push('');

    const sorted = [...components].sort((a, b) => b.risk.score - a.risk.score);

    for (const comp of sorted) {
      lines.push(
        `### ${severityEmoji(comp.risk.severity)} ${comp.name} (Score: ${comp.risk.score})`,
      );
      lines.push('');
      lines.push(`- **Type:** ${comp.type}`);
      lines.push(`- **Provider:** ${comp.provider}`);
      if (comp.modelName) lines.push(`- **Model:** ${comp.modelName}`);
      lines.push(`- **Location:** ${comp.location.filePath}`);
      if (comp.location.contextSnippet) {
        lines.push(`- **Context:** ${comp.location.contextSnippet}`);
      }

      if (comp.flags.length > 0) {
        lines.push('- **Flags:**');
        for (const flag of comp.flags) {
          const desc = FLAG_DESCRIPTIONS[flag] || flag.replace(/_/g, ' ');
          lines.push(`  - \`${flag}\`: ${desc}`);
        }
      }

      if (comp.risk.factors.length > 0) {
        lines.push('- **Risk Factors:**');
        for (const factor of comp.risk.factors) {
          lines.push(`  - ${factor}`);
        }
      }

      lines.push('');
    }
  } else {
    lines.push('## Findings');
    lines.push('');
    lines.push('No findings above the selected severity threshold.');
    lines.push('');
  }

  lines.push('---');
  lines.push('*Generated by [Trusera AI-BOM](https://trusera.dev)*');

  return lines.join('\n');
}

function generateJsonSummary(
  result: ScanResult,
  components: AIComponent[],
): Record<string, unknown> {
  return {
    scanTimestamp: result.scanTimestamp,
    targetPath: result.targetPath,
    aiBomVersion: result.aiBomVersion,
    summary: result.summary,
    findingsCount: components.length,
    findings: components.map((c) => ({
      name: c.name,
      type: c.type,
      provider: c.provider,
      modelName: c.modelName,
      severity: c.risk.severity,
      score: c.risk.score,
      flags: c.flags,
      factors: c.risk.factors,
    })),
  };
}
