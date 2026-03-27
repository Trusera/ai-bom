import { SidecarReporter } from '../../lib/sidecar/reporter';
import type { EvaluationResult } from '../../lib/sidecar/types';

const mockFetch = jest.fn();
global.fetch = mockFetch;

function makeEvaluationResult(overrides?: Partial<EvaluationResult>): EvaluationResult {
  return {
    allowed: true,
    enforcement: 'warn',
    violations: [],
    checks: [
      { name: 'pii_detection', passed: true, details: 'No PII detected' },
      { name: 'prompt_injection', passed: true, details: 'No injection detected' },
    ],
    timestamp: new Date().toISOString(),
    durationMs: 15,
    ...overrides,
  };
}

describe('SidecarReporter', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe('ensureRegistered', () => {
    it('should register agent with platform', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agent_id: 'agent-uuid-123' }),
      });

      const reporter = new SidecarReporter('https://api.trusera.io', 'tsk_test', 'my-agent');
      const agentId = await reporter.ensureRegistered();

      expect(agentId).toBe('agent-uuid-123');
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.trusera.io/api/v1/agents/register',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"framework":"n8n"'),
        }),
      );
    });

    it('should cache registration across calls', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agent_id: 'cached-id' }),
      });

      const reporter = new SidecarReporter('https://api.trusera.io', 'tsk_test', 'cache-test-agent');
      await reporter.ensureRegistered();
      await reporter.ensureRegistered();

      // Only one registration call, not two
      const registerCalls = mockFetch.mock.calls.filter(
        (c) => typeof c[0] === 'string' && c[0].includes('/agents/register'),
      );
      expect(registerCalls).toHaveLength(1);
    });

    it('should return "unregistered" on failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const reporter = new SidecarReporter('https://api.trusera.io', 'tsk_test', 'fail-agent');
      const agentId = await reporter.ensureRegistered();
      expect(agentId).toBe('unregistered');
    });
  });

  describe('track and flush', () => {
    it('should batch events and flush to platform', async () => {
      // Registration
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agent_id: 'agent-1' }),
      });
      // Batch flush
      mockFetch.mockResolvedValueOnce({ ok: true });

      const reporter = new SidecarReporter('https://api.trusera.io', 'tsk_test', 'flush-agent');
      const event = reporter.createEvaluationEvent(
        makeEvaluationResult(),
        { message: 'test' },
        'TestNode',
      );
      reporter.track(event);
      await reporter.flush();

      const batchCalls = mockFetch.mock.calls.filter(
        (c) => typeof c[0] === 'string' && c[0].includes('/events/batch'),
      );
      expect(batchCalls).toHaveLength(1);
    });

    it('should not flush when queue is empty', async () => {
      const reporter = new SidecarReporter('https://api.trusera.io', 'tsk_test', 'empty-agent');
      await reporter.flush();
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should silently handle flush errors', async () => {
      // Registration
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agent_id: 'agent-1' }),
      });
      // Batch flush fails
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const reporter = new SidecarReporter('https://api.trusera.io', 'tsk_test', 'error-flush-agent');
      const event = reporter.createEvaluationEvent(
        makeEvaluationResult(),
        { message: 'test' },
        'TestNode',
      );
      reporter.track(event);

      // Should not throw
      await expect(reporter.flush()).resolves.toBeUndefined();
    });
  });

  describe('createEvaluationEvent', () => {
    it('should create structured event from evaluation result', () => {
      const reporter = new SidecarReporter('https://api.trusera.io', 'tsk_test', 'event-agent');
      const result = makeEvaluationResult({
        violations: [{ policyName: 'pii', reason: 'SSN found', severity: 'high' }],
      });

      const event = reporter.createEvaluationEvent(result, { msg: 'data' }, 'MyNode', 'wf-123');

      expect(event.type).toBe('policy_evaluation');
      expect(event.agentName).toBe('event-agent');
      expect(event.workflowId).toBe('wf-123');
      expect(event.nodeName).toBe('MyNode');
      expect(event.payload).toHaveProperty('violations_count', 1);
      expect(event.payload).toHaveProperty('decision', 'deny');
      expect(event.id).toBeTruthy();
    });

    it('should set result to "allow" when no violations', () => {
      const reporter = new SidecarReporter('https://api.trusera.io', 'tsk_test', 'allow-agent');
      const event = reporter.createEvaluationEvent(
        makeEvaluationResult(),
        {},
        'Node',
      );
      expect(event.result).toBe('allow');
    });
  });
});
