#!/usr/bin/env npx tsx
/**
 * Load all 20 stress-test workflows into an n8n instance via REST API.
 *
 * Usage:
 *   npx tsx stress-test/load-workflows.ts [n8n-base-url] [api-key]
 *
 * Defaults:
 *   n8n-base-url = http://localhost:5679
 *   api-key      = $N8N_API_KEY env var
 */

import { ALL_WORKFLOWS } from './workflows';

const BASE_URL = (process.argv[2] || process.env.N8N_BASE_URL || 'http://localhost:5679').replace(/\/$/, '');
const API_KEY = process.argv[3] || process.env.N8N_API_KEY || '';

if (!API_KEY) {
  console.error('Error: No API key provided. Pass as 2nd arg or set N8N_API_KEY env var.');
  process.exit(1);
}

const headers: Record<string, string> = {
  'Content-Type': 'application/json',
  'X-N8N-API-KEY': API_KEY,
};

async function createWorkflow(workflow: (typeof ALL_WORKFLOWS)[number]): Promise<string> {
  const body = JSON.stringify({
    name: workflow.name,
    nodes: workflow.nodes,
    connections: workflow.connections,
    settings: workflow.settings || {},
    active: false,
  });

  const resp = await fetch(`${BASE_URL}/api/v1/workflows`, {
    method: 'POST',
    headers,
    body,
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Failed to create "${workflow.name}": ${resp.status} ${text}`);
  }

  const data = (await resp.json()) as { id: string };
  return data.id;
}

async function activateWorkflow(id: string): Promise<void> {
  const resp = await fetch(`${BASE_URL}/api/v1/workflows/${id}/activate`, {
    method: 'POST',
    headers,
  });

  if (!resp.ok) {
    // Activation may fail for workflows with webhook triggers if the webhook
    // path collides with existing ones — that's OK for testing.
    const text = await resp.text();
    console.warn(`  Warning: Could not activate workflow ${id}: ${text}`);
  }
}

async function main() {
  console.log(`Loading ${ALL_WORKFLOWS.length} workflows into ${BASE_URL}...\n`);

  const results: Array<{ name: string; id: string; active: boolean }> = [];

  for (const workflow of ALL_WORKFLOWS) {
    try {
      const id = await createWorkflow(workflow);
      console.log(`  Created: ${workflow.name} (id: ${id})`);

      // Try to activate
      await activateWorkflow(id);
      results.push({ name: workflow.name, id, active: true });
    } catch (err) {
      console.error(`  FAILED: ${workflow.name} — ${(err as Error).message}`);
      results.push({ name: workflow.name, id: '', active: false });
    }
  }

  console.log(`\n--- Summary ---`);
  console.log(`Total: ${results.length}`);
  console.log(`Created: ${results.filter((r) => r.id).length}`);
  console.log(`Failed: ${results.filter((r) => !r.id).length}`);
  console.log(`\nWorkflow IDs:`);
  for (const r of results) {
    if (r.id) console.log(`  ${r.name}: ${r.id}`);
  }
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
