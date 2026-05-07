import { describe, it, expect, beforeEach } from 'vitest';
import { mockInvoke } from './mocks/tauri.js';

describe('file list management', () => {
  beforeEach(() => {
    mockInvoke.mockReset();
  });

  it('get_seed_files returns file list', async () => {
    const mockFiles = [
      { filename: 'data1.xlsx', filepath: '/seed/data1.xlsx', basename: 'data1', row_count: 100 },
      { filename: 'data2.xlsx', filepath: '/seed/data2.xlsx', basename: 'data2', row_count: 50 },
    ];
    mockInvoke.mockResolvedValueOnce(mockFiles);
    const result = await mockInvoke('get_seed_files');
    expect(result).toHaveLength(2);
    expect(result[0].filename).toBe('data1.xlsx');
    expect(result[0].row_count).toBe(100);
  });

  it('add_seed_file calls invoke with path', async () => {
    mockInvoke.mockResolvedValueOnce('copied.xlsx');
    await mockInvoke('add_seed_file', { sourcePath: 'C:/Users/test/data.xlsx' });
    expect(mockInvoke).toHaveBeenCalledWith('add_seed_file', { sourcePath: 'C:/Users/test/data.xlsx' });
  });
});
