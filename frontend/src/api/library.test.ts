import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { entryFormats, entryStatuses } from "./library";

/**
 * The drift assertion for the client half of the domain contract.
 *
 * A domain's vocabulary starts in the registry (`domain/domains.py`), reaches the
 * published `StrEnum`s — which `backend/tests/test_domain.py` pins to the registry —
 * and is exported into `openapi.json`. These two arrays are the last copy in the chain,
 * hand-mirrored because the client is not generated, and nothing pinned them until now:
 * a third domain could add a status the server accepts and the client cannot name.
 *
 * The union is what a *filter* spans and what the API may return for any row. Which of
 * these values a given entry may hold is its domain's business and is published per item
 * type at `/api/item-types` (seam 5b, DEC-057); that is deliberately not mirrored here,
 * because a per-domain vocabulary compiled into the client is the thing seam 5b removed.
 */
// Read from the project root rather than relative to this module: under vitest
// `import.meta.url` is the dev server's URL, not a file path.
const schema = JSON.parse(
  readFileSync(resolve(process.cwd(), "openapi.json"), "utf8"),
) as {
  components: { schemas: Record<string, { enum?: string[] }> };
};

describe("the published vocabulary", () => {
  it("matches the statuses the API enumerates", () => {
    expect([...entryStatuses]).toEqual(
      schema.components.schemas.EntryStatus.enum,
    );
  });

  it("matches the formats the API enumerates", () => {
    expect([...entryFormats]).toEqual(
      schema.components.schemas.EntryFormat.enum,
    );
  });

  it("leaves the domain names to the registry", () => {
    // `ItemTypeName` is published for `?type=`, and is deliberately *not* mirrored into
    // a TypeScript union: every screen reads the domains from `GET /api/item-types`, so
    // a third domain must not need a frontend edit to be nameable.
    expect(schema.components.schemas.ItemTypeName.enum?.length).toBeGreaterThan(
      0,
    );
  });
});
