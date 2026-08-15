import "@testing-library/jest-dom/vitest";

import { installMatchMedia, setPrefersReducedMotion } from "./matchMedia";

/**
 * jsdom implements neither the Pointer Capture API nor `scrollIntoView`, and
 * Radix's Select and Dialog primitives call both while opening. Without these
 * shims every component-library interaction test throws
 * `target.hasPointerCapture is not a function` before it can assert anything.
 *
 * These stand in for browser APIs jsdom does not provide; the real behaviour is
 * exercised in the Playwright suite.
 */
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => undefined;
  Element.prototype.releasePointerCapture = () => undefined;
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => undefined;
}
/**
 * jsdom has no `ResizeObserver` at all, and cmdk constructs one as it mounts, so
 * the shelf picker's list throws before it can render. Nothing here measures
 * anything — every layout assertion lives in the Playwright suite, which runs in a
 * browser that has the real thing.
 */
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

/**
 * Every test runs under `prefers-reduced-motion: reduce` unless it opts out
 * with `setPrefersReducedMotion(false)`. Two reasons, and the second is the
 * important one:
 *
 * 1. Motion's fallback when `matchMedia` is absent is "animations allowed", and
 *    an unadvanced frameloop then leaves entering elements at `opacity: 0`.
 * 2. It makes the whole suite a standing proof of the Sprint 016 claim that
 *    every flow remains fully usable with motion disabled — add, score, delete,
 *    triage, import — at no authoring cost.
 */
installMatchMedia();
setPrefersReducedMotion(true);
