import { expect, type Page } from "@playwright/test";

/**
 * Durations a browser reports for "no animation at all". Chromium rounds the
 * reduced-motion CSS backstop (`0.01ms`) differently depending on the property,
 * and Motion writes a literal zero.
 */
export const stillDurations = ["0s", "0.00001s", "1e-05s"];

export interface SampledAnimation {
  /** A selector-ish description of what the animation was attached to. */
  target: string;
  duration: number;
}

/**
 * Watch every animation the browser starts, for as long as `run` takes.
 *
 * Reading `getAnimations()` after an interaction settles is useless: an
 * animation that has finished is no longer listed. So the sampler polls on
 * every frame and keeps what it saw, which is what makes "no row ever animated"
 * an assertable statement rather than a hopeful one.
 */
export async function sampleAnimations(
  page: Page,
  run: () => Promise<void>,
): Promise<SampledAnimation[]> {
  await page.evaluate(() => {
    const seen: { target: string; duration: number }[] = [];
    const describe = (element: Element): string => {
      if (element.closest("[data-entry-id]") === element) return "card";
      if (element.closest("[data-virtual-row]") === element) return "row";
      if (element.matches("[data-library-container]")) return "container";
      if (element.closest("[data-entry-id]")) return "inside-card";
      if (element.closest("[data-virtual-row]")) return "inside-row";
      return element.tagName.toLowerCase();
    };
    const tick = () => {
      for (const animation of document.getAnimations()) {
        const target = (animation.effect as KeyframeEffect | null)?.target;
        if (!target) continue;
        seen.push({
          target: describe(target),
          duration: Number(
            (animation.effect?.getTiming().duration as number | undefined) ?? 0,
          ),
        });
      }
      handle = requestAnimationFrame(tick);
    };
    let handle = requestAnimationFrame(tick);
    const store = window as unknown as {
      __motionSamples: typeof seen;
      __motionStop: () => void;
    };
    store.__motionSamples = seen;
    store.__motionStop = () => cancelAnimationFrame(handle);
  });
  await run();
  return page.evaluate(() => {
    const store = window as unknown as {
      __motionSamples: SampledAnimation[];
      __motionStop: () => void;
    };
    store.__motionStop();
    return store.__motionSamples;
  });
}

/** Every element whose motion this sprint is responsible for, by selector. */
export const animatedSurfaces = {
  card: "[data-entry-id='1']",
  container: "[data-library-container]",
  cover: "[data-entry-id='2'] img",
  scoreTrigger: "[data-entry-id='1'] [data-provisional]",
};

export async function readDurations(page: Page, selector: string) {
  return page
    .locator(selector)
    .first()
    .evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        transition: style.transitionDuration,
        animation: style.animationDuration,
      };
    });
}

export async function expectStill(page: Page, selector: string, label: string) {
  const durations = await readDurations(page, selector);
  expect(stillDurations, `${label} transition`).toContain(durations.transition);
  expect(stillDurations, `${label} animation`).toContain(durations.animation);
}

export async function expectAnimated(
  page: Page,
  selector: string,
  label: string,
) {
  const durations = await readDurations(page, selector);
  // The paired positive assertion. Without it, deleting every animation in the
  // application would leave the reduced-motion tests green -- which is exactly
  // how an invisible feedback layer survived thirteen sprints (DEC-024).
  expect(
    stillDurations.includes(durations.transition) &&
      stillDurations.includes(durations.animation),
    `${label} should animate without the reduced-motion preference, got ${JSON.stringify(durations)}`,
  ).toBe(false);
}
