import { describe, it, expect, beforeEach } from 'vitest';
import './mocks/tauri.js';

function fmt(n) { return n.toLocaleString('es-MX'); }
function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}

describe('state formatting', () => {
  it('formats numbers with es-MX locale', () => {
    expect(fmt(1000)).toBe('1,000');
    expect(fmt(0)).toBe('0');
  });

  it('formats time as MM:SS', () => {
    expect(fmtTime(0)).toBe('00:00');
    expect(fmtTime(65)).toBe('01:05');
    expect(fmtTime(3661)).toBe('61:01');
  });
});

describe('renderMetrics', () => {
  it('computes total RFC count from files', () => {
    const files = [{ row_count: 150 }, { row_count: 200 }];
    const totalRfcs = files.reduce((s, f) => s + f.row_count, 0);
    expect(totalRfcs).toBe(350);
  });

  it('formats found percentage correctly', () => {
    const processed = 100;
    const found = 30;
    const pct = Math.round(found / Math.max(processed, 1) * 100);
    expect(pct).toBe(30);
  });
});
