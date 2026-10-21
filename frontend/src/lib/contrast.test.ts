import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Both themes are held to WCAG AA here (Sprint 090): 4.5:1 for text, 3:1 for the
 * focus ring and the score ramp as a mark. The tokens are read from index.css
 * itself, so a value tuned there is checked the moment it changes.
 */
const css = readFileSync(resolve(__dirname, "../index.css"), "utf8");

function tokens(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  const block = css.slice(start, css.indexOf("}", start));
  return Object.fromEntries(
    [...block.matchAll(/--([a-z-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2]]),
  );
}

function luminance(hsl: string): number {
  const [h, s, l] = hsl.replace(/%/g, "").trim().split(/\s+/).map(Number);
  const a = (s / 100) * Math.min(l / 100, 1 - l / 100);
  const channel = (n: number) => {
    const k = (n + h / 30) % 12;
    const c = l / 100 - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(8) + 0.0722 * channel(4);
}

function ratio(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

const TEXT: [string, string][] = [
  ["foreground", "background"],
  ["foreground", "surface"],
  ["foreground", "surface-raised"],
  ["card-foreground", "card"],
  ["popover-foreground", "popover"],
  ["muted-foreground", "background"],
  ["muted-foreground", "surface"],
  ["muted-foreground", "muted"],
  ["primary-text", "background"],
  ["primary-text", "surface"],
  ["primary-foreground", "primary"],
  ["secondary-foreground", "secondary"],
  ["accent-foreground", "accent"],
  ["destructive", "background"],
  ["destructive-foreground", "destructive"],
  // A filled score chip writes its number in the page colour.
  ["background", "score-low"],
  ["background", "score-mid"],
  ["background", "score-high"],
  ["background", "score-top"],
];

const MARKS: [string, string][] = [
  ["ring", "background"],
  ["score-low", "background"],
  ["score-mid", "background"],
  ["score-high", "background"],
  ["score-top", "background"],
];

describe.each([
  ["Ink", ':root,\n  [data-theme="ink"]'],
  ["Paper", '[data-theme="paper"]'],
])("the %s theme", (_name, selector) => {
  const theme = tokens(selector);

  it.each(TEXT)("%s on %s reads at 4.5:1", (text, ground) => {
    expect(theme[text], text).toBeDefined();
    expect(theme[ground], ground).toBeDefined();
    expect(ratio(theme[text], theme[ground])).toBeGreaterThanOrEqual(4.5);
  });

  it.each(MARKS)("%s on %s stands out at 3:1", (mark, ground) => {
    expect(ratio(theme[mark], theme[ground])).toBeGreaterThanOrEqual(3);
  });
});
