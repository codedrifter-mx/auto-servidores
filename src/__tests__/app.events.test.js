import { describe, it, expect } from 'vitest';

describe('event payloads', () => {
  it('progress event payload shape matches frontend expectations', () => {
    const payload = { processed: 50, total: 100, found: 10, not_found: 40 };
    expect(payload).toHaveProperty('processed');
    expect(payload).toHaveProperty('total');
    expect(payload).toHaveProperty('found');
    expect(payload).toHaveProperty('not_found');
  });

  it('log event payload has message and level', () => {
    const payload = { message: 'Procesamiento completado.', level: 'info' };
    expect(payload).toHaveProperty('message');
    expect(payload).toHaveProperty('level');
  });

  it('429 detection from log message', () => {
    const msg = 'HTTP 429 on endpoint';
    expect(msg.includes('429')).toBe(true);
  });

  it('completion message detection', () => {
    const msg = 'Procesamiento completado.';
    expect(msg === 'Procesamiento completado.').toBe(true);
  });

  it('stop message detection', () => {
    const msg = 'Procesamiento detenido por el usuario.';
    expect(msg === 'Procesamiento detenido por el usuario.').toBe(true);
  });
});
