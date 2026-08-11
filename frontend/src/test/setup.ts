import "@testing-library/jest-dom/vitest";

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
