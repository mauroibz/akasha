import { defineConfig, devices } from "@playwright/test";

const DEV_PORT = 4173;
const PREVIEW_PORT = 4174;
const PRODUCTION_BUNDLE = /production-bundle\.spec\.ts/;
const SCRATCHPAD = /scratchpad/;
const INCLUDE_SCRATCHPAD = process.env.BOOK_TRACKER_INCLUDE_SCRATCHPAD === "1";
// The two 10,000-entry DOM-budget invariants in library.spec.ts (DEC-023) are
// load-sensitive: asserted mounted-row bounds assume the machine is not running
// the rest of the suite beside them. They run alone in the serial project
// below; every other spec runs parallel in the ordinary one. A future
// load-sensitive test goes in the same title grep, with its reason.
//
// Sprint 055 moved two more in, both never-green-in-parallel on three of
// three runs (DEC-114's measurement) and green on every serial run:
// - `changing sort crossfades the container and animates no row` and
//   `the mounted-DOM budget holds through a crossfade` — animation crossfades
//   sampled under load read mid-transition frames and inflated peaks;
// - the three library-view axe checks (`library in grid view…`, `library in
//   table view…`, `the library with web results on it…`) — axe's
//   color-contrast check samples the card caption, and under parallel load it
//   sampled mid-fade. The caption itself no longer fades (Sprint 055 dropped
//   the opacity modifier), but the assertions stay serial: a rendering-timing
//   sample under load is exactly the flakiness this project exists to remove,
//   and the failing test moved between them.
const HEAVY_LIBRARY =
  /the deterministic 10,000-entry library mounts only overscanned rows|the 10,000-entry library keeps its DOM budget with web results on the page|changing sort crossfades the container and animates no row|the mounted-DOM budget holds through a crossfade|library in (grid|table) view has no serious accessibility violations|the library with web results on it has no serious accessibility violations/;

export default defineConfig({
  testDir: "./e2e",
  testIgnore: INCLUDE_SCRATCHPAD ? [] : [SCRATCHPAD],
  // Parallel everywhere except the two load-sensitive invariants: the specs
  // stub their own API per test via page.route, so no worker shares state.
  fullyParallel: true,
  outputDir: "/tmp/akasha-playwright-results",
  reporter: "line",
  // Per-test bound, stated rather than Playwright's unstated 30 s default: a
  // wedged spec fails with its name instead of looking like slow work
  // (TESTING.md's Sprint 035 triage lesson).
  timeout: 60_000,
  use: { baseURL: `http://127.0.0.1:${DEV_PORT}`, trace: "retain-on-failure" },
  webServer: [
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${DEV_PORT}`,
      url: `http://127.0.0.1:${DEV_PORT}`,
      reuseExistingServer: false,
    },
    // The dev server does not chunk, so nothing in the chromium project can see
    // a bundle that is split wrongly. Sprint 018 found the production build had
    // been rendering a blank page since Sprint 017 (DEC-041) with every gate
    // green, which is what this second server exists to prevent.
    {
      command: `npm run build && npx vite preview --host 127.0.0.1 --port ${PREVIEW_PORT} --strictPort`,
      url: `http://127.0.0.1:${PREVIEW_PORT}`,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      testIgnore: INCLUDE_SCRATCHPAD
        ? [PRODUCTION_BUNDLE]
        : [PRODUCTION_BUNDLE, SCRATCHPAD],
      grepInvert: HEAVY_LIBRARY,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "heavy-library",
      // Both files carry load-sensitive tests: the 10,000-entry invariants in
      // library.spec.ts and the two Sprint 055 additions, one in each file.
      testMatch: /(library|accessibility)\.spec\.ts/,
      grep: HEAVY_LIBRARY,
      workers: 1,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "production-bundle",
      testMatch: PRODUCTION_BUNDLE,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://127.0.0.1:${PREVIEW_PORT}`,
      },
    },
  ],
});
