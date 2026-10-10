import { useCallback, useSyncExternalStore } from "react";

/** "system" follows the device; "light" and "dark" are an explicit choice kept on this device. */
export type Theme = "system" | "light" | "dark";

const STORAGE_KEY = "frutti-theme";
const listeners = new Set<() => void>();

function readTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // Storage can be blocked (private mode): fall back to the system theme.
  }
  return "system";
}

function applyTheme(theme: Theme): void {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

/** Call once before the first render so the page does not flash in the wrong theme. */
export function initTheme(): void {
  applyTheme(readTheme());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTheme(): { theme: Theme; setTheme: (theme: Theme) => void } {
  const theme = useSyncExternalStore(subscribe, readTheme, () => "system" as const);
  const setTheme = useCallback((next: Theme) => {
    try {
      if (next === "system") localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not remembered, but still applied for this visit.
    }
    applyTheme(next);
    listeners.forEach((listener) => listener());
  }, []);
  return { theme, setTheme };
}
