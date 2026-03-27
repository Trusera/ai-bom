import { TruseraToolInterceptor } from '../../lib/sidecar/toolInterceptor';
import type { PolicyGateEvaluator } from '../../lib/sidecar/policyGate';
import type { SidecarReporter } from '../../lib/sidecar/reporter';
import type { PolicyGateResult } from '../../lib/sidecar/types';

function makeGateResult(overrides?: Partial<PolicyGateResult>): PolicyGateResult {
  return {
    allowed: true,
    enforcement: 'block',
    violations: [],
    checks: [],
    timestamp: new Date().toISOString(),
    durationMs: 10,
    proposal: { toolName: 'test_tool', toolArgs: {}, reasoning: '', containsPii: false, dataSummary: '' },
    policySummaries: [],
    ...overrides,
  };
}

describe('TruseraToolInterceptor', () => {
  let interceptor: TruseraToolInterceptor;
  let mockEvaluator: jest.Mocked<PolicyGateEvaluator>;
  let mockReporter: jest.Mocked<SidecarReporter>;
  let fakeBaseTool: { prototype: { invoke: Function } };
  let originalInvoke: jest.Mock;

  beforeEach(() => {
    interceptor = new TruseraToolInterceptor();
    originalInvoke = jest.fn().mockResolvedValue('original result');
    fakeBaseTool = { prototype: { invoke: originalInvoke } };

    mockEvaluator = {
      evaluateToolCall: jest.fn().mockResolvedValue(makeGateResult()),
    } as any;

    mockReporter = {
      track: jest.fn(),
      flush: jest.fn().mockResolvedValue(undefined),
      createToolCallEvent: jest.fn().mockReturnValue({ id: 'event-1' }),
    } as any;
  });

  afterEach(() => {
    interceptor.uninstall();
  });

  it('should install on target and mark as installed', () => {
    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'block');
    expect(interceptor.isInstalled()).toBe(true);
    expect(fakeBaseTool.prototype.invoke).not.toBe(originalInvoke);
  });

  it('should pass clean tool calls through to original invoke', async () => {
    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'block');

    const toolInstance = { name: 'http_request' };
    const result = await fakeBaseTool.prototype.invoke.call(toolInstance, { url: 'test.com' });

    expect(mockEvaluator.evaluateToolCall).toHaveBeenCalledTimes(1);
    expect(originalInvoke).toHaveBeenCalled();
    expect(result).toBe('original result');
  });

  it('should block tool calls with violations in block mode', async () => {
    mockEvaluator.evaluateToolCall.mockResolvedValue(
      makeGateResult({
        violations: [{ policyName: 'pii', reason: 'PII detected', severity: 'high' }],
      }),
    );

    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'block');

    const toolInstance = { name: 'gmail_send_email' };
    await expect(
      fakeBaseTool.prototype.invoke.call(toolInstance, { body: 'SSN 123-45-6789' }),
    ).rejects.toThrow('[Trusera] BLOCKED: gmail_send_email');

    expect(originalInvoke).not.toHaveBeenCalled();
  });

  it('should allow with violations in warn mode', async () => {
    mockEvaluator.evaluateToolCall.mockResolvedValue(
      makeGateResult({
        violations: [{ policyName: 'pii', reason: 'PII detected', severity: 'high' }],
      }),
    );

    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();
    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'warn');

    const toolInstance = { name: 'gmail_send_email' };
    const result = await fakeBaseTool.prototype.invoke.call(toolInstance, { body: 'test' });

    expect(result).toBe('original result');
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('[Trusera] WARNING'));
    warnSpy.mockRestore();
  });

  it('should allow with violations in log mode silently', async () => {
    mockEvaluator.evaluateToolCall.mockResolvedValue(
      makeGateResult({
        violations: [{ policyName: 'pii', reason: 'PII detected', severity: 'high' }],
      }),
    );

    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'log');

    const toolInstance = { name: 'gmail_send_email' };
    const result = await fakeBaseTool.prototype.invoke.call(toolInstance, {});

    expect(result).toBe('original result');
  });

  it('should skip intercepting trusera_policy_gate', async () => {
    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'block');

    const toolInstance = { name: 'trusera_policy_gate' };
    await fakeBaseTool.prototype.invoke.call(toolInstance, { tool_name: 'test' });

    expect(mockEvaluator.evaluateToolCall).not.toHaveBeenCalled();
    expect(originalInvoke).toHaveBeenCalled();
  });

  it('should report events for intercepted calls', async () => {
    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'log');

    const toolInstance = { name: 'http_request' };
    await fakeBaseTool.prototype.invoke.call(toolInstance, { url: 'test.com' });

    expect(mockReporter.createToolCallEvent).toHaveBeenCalled();
    expect(mockReporter.track).toHaveBeenCalled();
    expect(mockReporter.flush).toHaveBeenCalled();
  });

  it('should uninstall and restore original', () => {
    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'block');
    interceptor.uninstall();

    expect(interceptor.isInstalled()).toBe(false);
    expect(fakeBaseTool.prototype.invoke).toBe(originalInvoke);
  });

  it('should not double-install', () => {
    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'block');
    const patchedInvoke = fakeBaseTool.prototype.invoke;

    interceptor._installOnTarget(fakeBaseTool, mockEvaluator, mockReporter, 'block');
    expect(fakeBaseTool.prototype.invoke).toBe(patchedInvoke);
  });
});
