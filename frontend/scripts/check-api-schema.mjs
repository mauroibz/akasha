// Sprint 088: `src/api/schema.d.ts` is generated from `openapi.json`, and this fails
// when the committed copy is stale. `src/api/contract.ts` holds the hand-written
// API types to the generated one, so a server-side rename fails `tsc`.
// Replaces check-openapi-types.mjs, which asserted ~15 property names by hand.
import { readFileSync, writeFileSync } from "node:fs";
import openapiTS, { astToString } from "openapi-typescript";
import { format, resolveConfig } from "prettier";

const target = new URL("../src/api/schema.d.ts", import.meta.url);
const ast = await openapiTS(new URL("../openapi.json", import.meta.url));
const options = (await resolveConfig(target.pathname)) ?? {};
const generated = await format(astToString(ast), {
  ...options,
  filepath: target.pathname,
});

if (process.argv.includes("--write")) {
  writeFileSync(target, generated);
  console.log("Wrote src/api/schema.d.ts from openapi.json.");
} else if (readFileSync(target, "utf8") !== generated) {
  console.error(
    "src/api/schema.d.ts is stale. Run `npm run api:generate` and commit it.",
  );
  process.exit(1);
} else {
  console.log("src/api/schema.d.ts matches openapi.json.");
}
