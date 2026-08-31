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
 * jsdom *defines* `window.scrollTo` but makes it throw `Not implemented`, so
 * unlike the shims above this cannot be guarded on absence — it has to replace
 * the throwing stub outright. @tanstack/react-virtual calls it on every mount
 * of a virtualized list, and each call printed a full stack trace to stderr:
 * harmless, but it buried real output under pages of noise. Scrolling is not
 * what these tests assert; the Playwright suite exercises the real thing.
 */
window.scrollTo = () => undefined;
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
