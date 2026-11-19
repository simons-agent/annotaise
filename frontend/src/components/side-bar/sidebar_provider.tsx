'use client';

import { createContext, useContext, useState, useMemo, useCallback, type ReactNode } from 'react';

// Below Tailwind's `md` breakpoint the open sidebar would take almost half of a
// phone screen, so it starts collapsed there unless the user chose otherwise.
export const NARROW_SCREEN_QUERY = '(max-width: 767px)';

export function initialSidebarOpen(stored: string | null, isNarrowScreen: boolean): boolean {
  if (stored !== null) return stored === 'true';
  return !isNarrowScreen;
}

type SidebarContextValue = {
  isOpen: boolean;
  toggle: () => void;
};

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    const stored = window.localStorage.getItem('sidebar-open');
    // Persisted in localStorage so the collapsed state survives navigation between pages.
    return initialSidebarOpen(stored, window.matchMedia?.(NARROW_SCREEN_QUERY).matches ?? false);
  });

  const toggle = useCallback(() => {
    setIsOpen((prev) => {
      const next = !prev;
      if (typeof window !== 'undefined') {
        window.localStorage.setItem('sidebar-open', String(next));
      }
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({
      isOpen,
      toggle,
    }),
    [isOpen, toggle]
  );

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
}

export function useSidebarState() {
  return useContext(SidebarContext);
}
