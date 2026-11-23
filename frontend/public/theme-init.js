// The theme is set before the first paint so a Paper reader never sees a flash
// of Ink (Sprint 090). The same key and rules as src/lib/theme.ts, and the same
// list of themes, which a test holds the two to (Sprint 148). A file rather than
// an inline script so the Content-Security-Policy can say script-src 'self'
// (Sprint 128).
/* global localStorage, window, document */
(function () {
  var themes = ["paper", "ink", "moss", "claret", "dusk", "sakura"];
  var choice = "system";
  try {
    choice = localStorage.getItem("akasha:theme") || "system";
  } catch {
    // Storage blocked (private mode, policy): follow the system preference.
  }
  var theme =
    themes.indexOf(choice) !== -1
      ? choice
      : window.matchMedia("(prefers-color-scheme: light)").matches
        ? "paper"
        : "ink";
  document.documentElement.dataset.theme = theme;
})();
