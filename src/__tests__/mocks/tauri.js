import { vi } from 'vitest';

export const mockInvoke = vi.fn();
export const mockListen = vi.fn(() => Promise.resolve(vi.fn()));
export const mockOpen = vi.fn();
export const mockAsk = vi.fn();
export const mockGetCurrentWindow = vi.fn(() => ({
  destroy: vi.fn(),
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: mockInvoke,
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: mockListen,
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: mockOpen,
  ask: mockAsk,
}));

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: mockGetCurrentWindow,
}));
