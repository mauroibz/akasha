import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  entryFormats,
  entryStatuses,
  fetchProviderCover,
  refreshItem,
} from "./library";

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

describe("provider-refresh error messages", () => {
  afterEach(() => vi.restoreAllMocks());

  /**
   * The one canned sentence used to fire for every refusal — a disabled
   * provider, a fetch that failed live, an item with no source at all — which
   * left the owner guessing at a cause the server already named.
   */
  it("surfaces the server's own reason instead of one canned sentence", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "provider_failure",
            message: "Metadata could not be fetched",
          },
        }),
        { status: 502 },
      ),
    );
    await expect(refreshItem(3)).rejects.toThrow(
      "Metadata could not be fetched",
    );
  });

  it("falls back to a generic message when the body cannot be read", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not json", { status: 500 }),
    );
    await expect(refreshItem(3)).rejects.toThrow(
      "Provider refresh failed; your metadata was not changed",
    );
  });

  it("reports why a cover fetch failed, the same way", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "cover_unavailable",
            message: "The provider has no cover for this item",
          },
        }),
        { status: 422 },
      ),
    );
    await expect(fetchProviderCover(3)).rejects.toThrow(
      "The provider has no cover for this item",
    );
  });
});
