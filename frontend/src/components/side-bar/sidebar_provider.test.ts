import { describe, expect, it } from 'vitest';
import { initialSidebarOpen } from './sidebar_provider';

describe('initialSidebarOpen', () => {
  it('a stored choice wins', () => {
    expect(initialSidebarOpen('true', true)).toBe(true);
    expect(initialSidebarOpen('false', false)).toBe(false);
  });

  it('without a stored choice the sidebar starts open on wide and closed on narrow screens', () => {
    expect(initialSidebarOpen(null, false)).toBe(true);
    expect(initialSidebarOpen(null, true)).toBe(false);
  });
});
