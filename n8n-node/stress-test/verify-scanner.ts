#!/usr/bin/env npx tsx
/**
 * Verify scanner results against expected flags for all 20 stress-test workflows.
 * Runs the scanner locally (no n8n instance needed).
 */

import { scanWorkflow, scanWorkflows } from '../lib/scanner';
import { ALL_WORKFLOWS } from './workflows';

interface Expectation {
  name: string;
  minComponents: number;
  requiredFlags: string[];
  forbiddenFlags: string[];
  expectedSeverity?: string;
  minScore: number;
  maxScore: number;
}

const EXPECTATIONS: Expectation[] = [
  // SAFE (1-5): score 0, no harmful flags
  { name: '01', minComponents: 2, requiredFlags: [], forbiddenFlags: ['webhook_no_auth', 'hardcoded_api_key', 'hardcoded_credentials', 'code_http_tools', 'mcp_unknown_server', 'internet_facing'], minScore: 0, maxScore: 0, expectedSeverity: 'low' },
  { name: '02', minComponents: 4, requiredFlags: [], forbiddenFlags: ['webhook_no_auth', 'hardcoded_api_key', 'hardcoded_credentials', 'code_http_tools', 'internet_facing'], minScore: 0, maxScore: 0, expectedSeverity: 'low' },
  { name: '03', minComponents: 3, requiredFlags: [], forbiddenFlags: ['webhook_no_auth', 'hardcoded_api_key', 'hardcoded_credentials', 'code_http_tools', 'internet_facing'], minScore: 0, maxScore: 0, expectedSeverity: 'low' },
  { name: '04', minComponents: 3, requiredFlags: [], forbiddenFlags: ['webhook_no_auth', 'hardcoded_api_key', 'hardcoded_credentials', 'internet_facing'], minScore: 0, maxScore: 0, expectedSeverity: 'low' },
  { name: '05', minComponents: 2, requiredFlags: [], forbiddenFlags: ['webhook_no_auth', 'hardcoded_api_key', 'hardcoded_credentials', 'internet_facing'], minScore: 0, maxScore: 0, expectedSeverity: 'low' },

  // MEDIUM (6-10)
  { name: '06', minComponents: 1, requiredFlags: ['webhook_no_auth', 'internet_facing', 'no_error_handling', 'unpinned_model'], forbiddenFlags: [], minScore: 40, maxScore: 100 },
  { name: '07', minComponents: 2, requiredFlags: ['unpinned_model', 'no_error_handling'], forbiddenFlags: ['webhook_no_auth'], minScore: 10, maxScore: 30 },
  { name: '08', minComponents: 3, requiredFlags: ['no_error_handling'], forbiddenFlags: ['webhook_no_auth', 'internet_facing'], minScore: 5, maxScore: 20 },
  { name: '09', minComponents: 2, requiredFlags: ['mcp_unknown_server', 'no_error_handling'], forbiddenFlags: ['webhook_no_auth'], minScore: 20, maxScore: 50 },
  { name: '10', minComponents: 2, requiredFlags: ['deprecated_model', 'no_error_handling'], forbiddenFlags: ['webhook_no_auth'], minScore: 15, maxScore: 40 },

  // HIGH (11-15)
  { name: '11', minComponents: 2, requiredFlags: ['webhook_no_auth', 'internet_facing', 'code_http_tools', 'no_error_handling'], forbiddenFlags: [], minScore: 60, maxScore: 100 },
  { name: '12', minComponents: 3, requiredFlags: ['webhook_no_auth', 'internet_facing', 'no_error_handling'], forbiddenFlags: [], minScore: 40, maxScore: 100 },
  { name: '13', minComponents: 2, requiredFlags: ['hardcoded_api_key', 'no_error_handling'], forbiddenFlags: ['webhook_no_auth'], minScore: 30, maxScore: 60 },
  { name: '14', minComponents: 2, requiredFlags: ['webhook_no_auth', 'internet_facing', 'mcp_unknown_server', 'no_error_handling'], forbiddenFlags: [], minScore: 50, maxScore: 100 },
  { name: '15', minComponents: 3, requiredFlags: ['deprecated_model', 'no_error_handling'], forbiddenFlags: ['webhook_no_auth'], minScore: 15, maxScore: 60 },

  // CRITICAL (16-20)
  { name: '16', minComponents: 2, requiredFlags: ['webhook_no_auth', 'internet_facing', 'code_http_tools', 'no_error_handling'], forbiddenFlags: [], minScore: 70, maxScore: 100 },
  { name: '17', minComponents: 3, requiredFlags: ['no_error_handling'], forbiddenFlags: [], minScore: 30, maxScore: 100 },
  { name: '18', minComponents: 4, requiredFlags: ['webhook_no_auth', 'internet_facing', 'no_error_handling', 'deprecated_model'], forbiddenFlags: [], minScore: 60, maxScore: 100 },
  { name: '19', minComponents: 2, requiredFlags: ['webhook_no_auth', 'internet_facing', 'mcp_unknown_server', 'no_error_handling'], forbiddenFlags: [], minScore: 50, maxScore: 100 },
  { name: '20', minComponents: 5, requiredFlags: ['webhook_no_auth', 'internet_facing', 'no_error_handling', 'deprecated_model'], forbiddenFlags: [], minScore: 60, maxScore: 100 },
];

let passed = 0;
let failed = 0;
const failures: string[] = [];

for (let i = 0; i < ALL_WORKFLOWS.length; i++) {
  const workflow = ALL_WORKFLOWS[i];
  const expect = EXPECTATIONS[i];
  const prefix = `[${expect.name}] ${workflow.name}`;

  const components = scanWorkflow(workflow, workflow.name);
  const allFlags = new Set(components.flatMap((c) => c.flags));
  const highestScore = Math.max(0, ...components.map((c) => c.risk.score));

  let ok = true;
  const issues: string[] = [];

  // Check min components
  if (components.length < expect.minComponents) {
    issues.push(`Expected >= ${expect.minComponents} components, got ${components.length}`);
    ok = false;
  }

  // Check required flags (at least one component should have each)
  for (const flag of expect.requiredFlags) {
    if (!allFlags.has(flag)) {
      issues.push(`Missing required flag: ${flag}`);
      ok = false;
    }
  }

  // Check forbidden flags
  for (const flag of expect.forbiddenFlags) {
    if (allFlags.has(flag)) {
      issues.push(`Found forbidden flag: ${flag}`);
      ok = false;
    }
  }

  // Check score range
  if (highestScore < expect.minScore) {
    issues.push(`Score ${highestScore} below min ${expect.minScore}`);
    ok = false;
  }
  if (highestScore > expect.maxScore) {
    issues.push(`Score ${highestScore} above max ${expect.maxScore}`);
    ok = false;
  }

  if (ok) {
    console.log(`  PASS ${prefix} — ${components.length} components, score ${highestScore}, flags: [${[...allFlags].join(', ')}]`);
    passed++;
  } else {
    console.log(`  FAIL ${prefix}`);
    for (const issue of issues) {
      console.log(`       - ${issue}`);
    }
    console.log(`       Detected flags: [${[...allFlags].join(', ')}]`);
    console.log(`       Components: ${components.length}, Highest score: ${highestScore}`);
    failures.push(prefix);
    failed++;
  }
}

// Also test multi-workflow scan
console.log('\n--- Multi-workflow scan ---');
const allData = ALL_WORKFLOWS.map((w) => ({ data: w as unknown, filePath: w.name }));
const result = scanWorkflows(allData);
console.log(`  Total components: ${result.components.length}`);
console.log(`  Workflows scanned: ${result.summary.totalFilesScanned}`);
console.log(`  Highest risk: ${result.summary.highestRiskScore}`);
console.log(`  By severity: ${JSON.stringify(result.summary.bySeverity)}`);

console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
if (failures.length > 0) {
  console.log('Failures:');
  for (const f of failures) console.log(`  - ${f}`);
  process.exit(1);
}
