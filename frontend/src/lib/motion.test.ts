import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { motionDuration, useMotionPresets } from "@/lib/motion";
import { setPrefersReducedMotion } from "@/test/matchMedia";

/**
 * Every number reachable from a preset, so a stray duration cannot hide.
 * Resting values (`opacity: 1`) are numbers too, so callers filter by path:
 * what must be zero under reduced motion is timing, not target state.
 */
function numbers(value: unknown, path = ""): [string, number][] {
  if (typeof value === "number") return [[path, value]];
  if (Array.isArray(value))
    return value.flatMap((item, i) => numbers(item, `${path}[${i}]`));
  if (value && typeof value === "object")
    return Object.entries(value).flatMap(([key, item]) =>
      numbers(item, path ? `${path}.${key}` : key),
    );
  return [];
}

function keys(value: unknown): string[] {
  if (Array.isArray(value)) return value.flatMap(keys);
  if (value && typeof value === "object")
    return Object.entries(value).flatMap(([key, item]) => [key, ...keys(item)]);
  return [];
}

function presets(reduced: boolean) {
  setPrefersReducedMotion(reduced);
  return renderHook(() => useMotionPresets()).result.current;
}

describe("useMotionPresets", () => {
  it("reports the preference it was built from", () => {
    expect(presets(true).reduced).toBe(true);
    expect(presets(false).reduced).toBe(false);
  });

  it("animates transform and opacity when motion is allowed", () => {
    const p = presets(false);
    expect(p.crossfade.initial).toEqual({ opacity: 0 });
    expect(keys(p.formEnter)).toContain("y");
    expect(keys(p.commitPop)).toContain("scale");
    expect(
      numbers(p.crossfade).some(
        ([path, n]) => path.endsWith("transition.duration") && n > 0,
      ),
    ).toBe(true);
  });

  it("reduces every preset to nothing when the preference is set", () => {
    const p = presets(true);
    const all = {
      crossfade: p.crossfade,
      panel: p.panel,
      formEnter: p.formEnter,
      actionBar: p.actionBar,
      commitPop: p.commitPop,
      press: p.press,
      staggerItem: p.staggerItem(4),
    };
    // A transform or blur that starts off-target is a visible animation even at
    // duration zero, because the first painted frame shows the offset.
    for (const key of keys(all))
      expect(["y", "x", "scale", "filter"]).not.toContain(key);
    // Timing only: every duration, delay, stiffness and mass is gone.
    const timings = numbers(all).filter(([path]) =>
      path.includes("transition."),
    );
    expect(timings.length).toBeGreaterThan(0);
    for (const [path, value] of timings)
      expect([path, value]).toEqual([path, 0]);
  });

  it("never sets an entering initial state under reduced motion", () => {
    const p = presets(true);
    expect(p.crossfade.initial).toBe(false);
    expect(p.panel.initial).toBe(false);
    expect(p.formEnter.initial).toBe(false);
    expect(p.actionBar.initial).toBe(false);
  });

  it("clamps the stagger delay so a long result list still lands quickly", () => {
    const p = presets(false);
    const delay = (index: number) =>
      (p.staggerItem(index).show as { transition: { delay: number } })
        .transition.delay;
    expect(delay(0)).toBe(0);
    expect(delay(4)).toBeCloseTo(4 * motionDuration.stagger);
    // The 30th result must not wait a second to appear.
    expect(delay(30)).toBe(delay(8));
  });
});
