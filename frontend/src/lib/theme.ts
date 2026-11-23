/**
 * The reader's theme (Sprint 090): *Ink*, *Paper*, or whatever the device prefers;
 * since Sprint 148 (DEC-193) also one of four presets.
 *
 * Kept per browser rather than on the account: a phone in a bright kitchen and a
 * laptop at night want different things. `public/theme-init.js` runs the same
 * resolution before first paint; this module keeps the page in step afterwards, and
 * a test holds the two to the same list.
 */
export const THEMES = [
  {
    id: "paper",
    label: "Paper",
    hint: "Warm, like a page",
    page: "#f4f0e6",
    card: "#d8cdb6",
    accent: "#e9a23b",
  },
  {
    id: "ink",
    label: "Ink",
    hint: "Dark, and warm",
    page: "#0d0c0a",
    card: "#2c2820",
    accent: "#fbbf24",
  },
  {
    id: "moss",
    label: "Moss",
    hint: "Dark, and green",
    page: "#0e130f",
    card: "#263328",
    accent: "#9ccc65",
  },
  {
    id: "claret",
    label: "Claret",
    hint: "Dark, like wine",
    page: "#140c0e",
    card: "#372226",
    accent: "#e0736f",
  },
  {
    id: "dusk",
    label: "Dusk",
    hint: "Dark, and blue",
    page: "#0d0f18",
    card: "#282e48",
    accent: "#8fa4ff",
  },
  {
    id: "sakura",
    label: "Sakura",
    hint: "Light, and pink",
    page: "#f7eef0",
    card: "#e6d2d7",
    accent: "#e58aa5",
  },
] as const;

export type Theme = (typeof THEMES)[number]["id"];
export type ThemeChoice = "system" | Theme;

export const THEME_KEY = "akasha:theme";
const LIGHT_QUERY = "(prefers-color-scheme: light)";

function isTheme(value: string | null): value is Theme {
  return THEMES.some((theme) => theme.id === value);
}

export function readThemeChoice(): ThemeChoice {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return isTheme(value) ? value : "system";
  } catch {
    return "system";
  }
}

/** The device decides between *Paper* and *Ink* only; a preset is always a choice. */
export function resolveTheme(choice: ThemeChoice): Theme {
  if (choice !== "system") return choice;
  return window.matchMedia?.(LIGHT_QUERY).matches ? "paper" : "ink";
}

export function applyTheme(choice: ThemeChoice): void {
  const theme = resolveTheme(choice);
  document.documentElement.dataset.theme = theme;
  const page = THEMES.find((row) => row.id === theme)?.page ?? "#0d0c0a";
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", page);
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
