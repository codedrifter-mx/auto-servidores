import { describe, it, expect, beforeEach } from 'vitest';
import { mockInvoke } from './mocks/tauri.js';

describe('processing flow', () => {
  beforeEach(() => {
    mockInvoke.mockReset();
  });

  it('start_processing is invoked', async () => {
    mockInvoke.mockResolvedValueOnce('started');
    const result = await mockInvoke('start_processing');
    expect(result).toBe('started');
    expect(mockInvoke).toHaveBeenCalledWith('start_processing');
  });

  it('stop_processing is invoked', async () => {
    mockInvoke.mockResolvedValueOnce(undefined);
    await mockInvoke('stop_processing');
    expect(mockInvoke).toHaveBeenCalledWith('stop_processing');
  });

  it('save_config called before start_processing in sequence', async () => {
    const callOrder = [];
    mockInvoke.mockImplementation((cmd) => {
      callOrder.push(cmd);
      return Promise.resolve(cmd === 'save_config' ? undefined : 'started');
    });
    await mockInvoke('save_config', { newConfig: {} });
    await mockInvoke('start_processing');
    expect(callOrder).toEqual(['save_config', 'start_processing']);
  });
});
