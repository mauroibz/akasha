// The theme is set before the first paint so a Paper reader never sees a flash
// of Ink (Sprint 090). The same key and rules as src/lib/theme.ts. A file rather
// than an inline script so the Content-Security-Policy can say script-src 'self'
// (Sprint 128).
/* global localStorage, window, document */
(function () {
  var choice = "system";
  try {
    choice = localStorage.getItem("akasha:theme") || "system";
  } catch {
    // Storage blocked (private mode, policy): follow the system preference.
  }
  var theme =
    choice === "paper" || choice === "ink"
      ? choice
      : window.matchMedia("(prefers-color-scheme: light)").matches
        ? "paper"
        : "ink";
  document.documentElement.dataset.theme = theme;
})();
