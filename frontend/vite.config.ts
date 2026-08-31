import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const MOTION = new Set([
  "motion",
  "framer-motion",
  "motion-dom",
  "motion-utils",
]);
const FORMS = new Set(["react-hook-form", "zod"]);
const UI = new Set([
  "class-variance-authority",
  "clsx",
  "cmdk",
  "lucide-react",
  "sonner",
  "tailwind-merge",
  "vaul",
]);

export default defineConfig({
  plugins: [react()],
  // Pre-bundled at server start rather than discovered during the first
  // navigation. Vite force-reloads the page when it optimizes a dependency it
  // meets mid-session, which silently discards whatever the user (or
  // Playwright) was doing at that moment. Sprint 015 added enough dependencies
  // that this became a reproducible first-run failure.
  optimizeDeps: {
    include: [
      "@hookform/resolvers/zod",
      "@tanstack/react-query",
      "@tanstack/react-virtual",
      "class-variance-authority",
      "clsx",
      "cmdk",
      "lucide-react",
      "motion/react",
      "react",
      "react-dom",
      "react-hook-form",
      "react-router-dom",
      "sonner",
      "tailwind-merge",
      "zod",
    ],
  },
  build: {
    rollupOptions: {
      output: {
        // Split by change rate, not by size. The framework and data layers
        // barely move between sprints, so a browser that has them cached keeps
        // them across a deploy that only touched application code.
        //
        // This is a function and not the object form on purpose. Naming
        // packages ("react", "react-dom") assigns only those exact entry
        // modules; their transitive runtime — scheduler, jsx-runtime,
        // use-sync-external-store — stays unassigned and lands wherever Rollup
        // puts it, which produced a cycle where the react chunk imported the
        // query chunk and React was undefined at evaluation time. The whole
        // application rendered a blank page in every production build, and no
        // test caught it because Playwright runs against the dev server, which
        // does not chunk at all.
        //
        // Falling through to one vendor chunk means a module can never be left
        // unassigned, so that failure cannot come back by adding a dependency.
        // Every group below depends on vendor and nothing in vendor depends on
        // them, which is what keeps the graph acyclic.
        manualChunks(id: string) {
          const match =
            /[\\/]node_modules[\\/](@[^\\/]+[\\/][^\\/]+|[^\\/]+)/.exec(id);
          const pkg = match?.[1]?.replace(/\\/g, "/");
          if (pkg === undefined) return undefined;
          // Matching on the resolved package name rather than on a substring of
          // the path: "motion" also has to catch framer-motion, motion-dom and
          // motion-utils, which are its transitive runtime and are what a
          // hand-written list forgets.
          if (MOTION.has(pkg)) return "motion";
          if (pkg.startsWith("@tanstack/")) return "query";
          if (FORMS.has(pkg) || pkg.startsWith("@hookform/")) return "forms";
          if (UI.has(pkg) || pkg.startsWith("@radix-ui/")) return "ui";
          return "vendor";
        },
      },
    },
    // Deliberately below Rollup's 500 kB default rather than above it: the point
    // of the split is that no chunk should approach the old 696 kB again, and a
    // limit raised to accommodate a regression would not notice one (DEC-037).
    chunkSizeWarningLimit: 300,
  },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    proxy: {
      "/api": process.env.BOOK_TRACKER_E2E_BACKEND ?? "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
    // Bounded like the backend: a wedged test fails with its name instead of
    // looking like slow work. 15 s is measured headroom — the slowest current
    // test is ~2.4 s (HomePage's provider-search cases).
    testTimeout: 15_000,
  },
});
