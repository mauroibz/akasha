import { flushSync } from "react-dom";
import type { NavigateFunction, NavigateOptions, To } from "react-router-dom";

/**
 * Navigate inside the browser's view transition, so elements that share a
 * `view-transition-name` (a cover on the library card and on the detail page)
 * morph from one page to the other (Sprint 092).
 *
 * React Router's own `viewTransition` option only works under its data router,
 * and this application uses the declarative `<BrowserRouter>`, so the transition
 * is started here: the navigation commits synchronously inside it, and the new
 * page must draw its shared element in that first frame (the detail page starts
 * from the list's cached entry for that reason). Without the API, or with reduced
 * motion, it is an ordinary navigation.
 */
export function navigateWithTransition(
  navigate: NavigateFunction,
  to: To,
  options?: NavigateOptions,
): void {
  const start = (
    document as Document & {
      startViewTransition?: (update: () => void) => unknown;
    }
  ).startViewTransition;
  const reduced = window.matchMedia?.(
    "(prefers-reduced-motion: reduce)",
  ).matches;
  if (!start || reduced) {
    void navigate(to, options);
    return;
  }
  start.call(document, () => {
    flushSync(() => {
      void navigate(to, options);
    });
  });
}
