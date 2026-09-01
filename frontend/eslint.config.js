import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "e2e/scratchpad"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      // `m` renders under the AppShell's LazyMotion provider and carries only
      // the features declared there. The eager `motion` factory bundles every
      // feature, including the projection code that makes `layout` animations
      // work in a virtualized list.
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "motion/react",
              importNames: ["motion"],
              message:
                "Import `m` from motion/react and render it under the AppShell LazyMotion provider.",
            },
          ],
        },
      ],
    },
  },
  {
    // Technical spec section 8 and DEC-023: virtual rows carry no enter, exit
    // or layout animation. Sort and filter changes crossfade the container, in
    // HomePage. This is a rule with a history: rows unmount as they scroll out
    // and would re-animate on every return.
    files: ["src/features/library/VirtualLibrary.tsx"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["motion", "motion/*"],
              message:
                "Virtualized rows are never animated (technical spec section 8, DEC-023). Animate the list container in HomePage instead.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["scripts/**/*.mjs", "*.config.{js,ts}"],
    languageOptions: { globals: globals.node },
  },
);
