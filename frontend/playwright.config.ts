import { defineConfig, devices } from "@playwright/test";

const DEV_PORT = 4173;
const PREVIEW_PORT = 4174;
const PRODUCTION_BUNDLE = /production-bundle\.spec\.ts/;
const SCRATCHPAD = /scratchpad/;
const INCLUDE_SCRATCHPAD = process.env.BOOK_TRACKER_INCLUDE_SCRATCHPAD === "1";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: INCLUDE_SCRATCHPAD ? [] : [SCRATCHPAD],
  fullyParallel: false,
  outputDir: "/tmp/akasha-playwright-results",
  reporter: "line",
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
