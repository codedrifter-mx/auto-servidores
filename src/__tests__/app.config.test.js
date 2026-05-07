import { describe, it, expect, beforeEach } from 'vitest';
import { mockInvoke } from './mocks/tauri.js';

describe('config form population', () => {
  beforeEach(() => {
    mockInvoke.mockReset();
  });

  it('invoke is called with save_config when saving config', async () => {
    const testConfig = {
      api: { base_url: 'https://example.com', endpoints: { search: '/search', history: '/history' }, default_coll_name: '100', timeout: 60, max_retries: 5, retry_base_delay: 2.0 },
      cache: { enabled: true, db_path: '.cache/db', ttl_seconds: 3600 },
      rate_limit: { max_concurrent: 10, min_interval: 0.15, cooldown_base: 5.0, cooldown_max: 60.0, inter_batch_delay: 1.5 },
      filters: { years_to_check: [2025, 2026], common_filters: { tipoDeclaracion: 'MODIFICACION', institucionReceptora: 'TEST' } },
      processing: { batch_size: 100, max_workers: 50 },
      output: { dir: 'output', found_suffix: '_ENCONTRADOS', not_found_suffix: '_NO_ENCONTRADOS' },
    };
    mockInvoke.mockResolvedValueOnce(undefined);
    await mockInvoke('save_config', { newConfig: testConfig });
    expect(mockInvoke).toHaveBeenCalledWith('save_config', { newConfig: testConfig });
  });

  it('get_config returns config object', async () => {
    mockInvoke.mockResolvedValueOnce({ api: { base_url: 'https://test.com' } });
    const result = await mockInvoke('get_config');
    expect(result.api.base_url).toBe('https://test.com');
  });
});
