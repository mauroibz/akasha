/**
 * The reader's theme (Sprint 090): *Ink*, *Paper*, or whatever the device prefers.
 *
 * Kept per browser rather than on the account: a phone in a bright kitchen and a
 * laptop at night want different things. index.html runs the same resolution inline
 * before first paint; this module keeps the page in step afterwards.
 */
export type ThemeChoice = "system" | "paper" | "ink";
export type Theme = "paper" | "ink";

export const THEME_KEY = "akasha:theme";
const LIGHT_QUERY = "(prefers-color-scheme: light)";

export function readThemeChoice(): ThemeChoice {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === "paper" || value === "ink" ? value : "system";
  } catch {
    return "system";
  }
}

export function resolveTheme(choice: ThemeChoice): Theme {
  if (choice !== "system") return choice;
  return window.matchMedia?.(LIGHT_QUERY).matches ? "paper" : "ink";
}

export function applyTheme(choice: ThemeChoice): void {
  const theme = resolveTheme(choice);
  document.documentElement.dataset.theme = theme;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", theme === "paper" ? "#f4f0e6" : "#0d0c0a");
}

export function saveThemeChoice(choice: ThemeChoice): void {
  try {
    if (choice === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, choice);
  } catch {
    /* private mode: the choice holds for this page only */
  }
  applyTheme(choice);
}

/** Follow the device while the choice is "system"; returns the unsubscribe. */
export function followDeviceTheme(): () => void {
  const query = window.matchMedia?.(LIGHT_QUERY);
  if (!query) return () => undefined;
  const onChange = () => {
    if (readThemeChoice() === "system") applyTheme("system");
  };
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
