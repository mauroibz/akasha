import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

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
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query", "@tanstack/react-virtual"],
          motion: ["motion", "motion/react"],
          forms: ["react-hook-form", "@hookform/resolvers/zod", "zod"],
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
  },
});
