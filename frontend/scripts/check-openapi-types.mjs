import { readFileSync } from "node:fs";

const schema = JSON.parse(
  readFileSync(new URL("../openapi.json", import.meta.url), "utf8"),
);
const components = schema.components?.schemas ?? {};
const expected = {
  EntryListResponse: ["items", "next_cursor", "total", "facets"],
  EntryResponse: [
    "id",
    "item_id",
    "status",
    "score",
    "item",
    "shelves",
    "formats",
    "score_provisional",
  ],
  ItemResponse: ["id", "type", "title", "creator", "cover_url", "metadata"],
  ItemTypeResponse: [
    "id",
    "label",
    "fields",
    "statuses",
    "default_status",
    "entry_fields",
    "formats",
    "entry_panel_label",
  ],
  FieldSpecResponse: ["name", "label", "type", "multiplicity"],
  StatusSpecResponse: ["value", "label", "choosable", "hotkey"],
  FormatSpecResponse: ["value", "label"],
  FacetsResponse: ["status_counts", "status_counts_by_type", "format_counts"],
  ShelfResponse: ["id", "name", "slug", "entry_count"],
};

for (const [name, properties] of Object.entries(expected)) {
  const actual = components[name]?.properties;
  if (!actual) throw new Error(`OpenAPI schema ${name} is missing`);
  for (const property of properties) {
    if (!(property in actual))
      throw new Error(`OpenAPI schema ${name}.${property} is missing`);
  }
}

// The published vocabularies must exist here, because `src/api/library.ts` mirrors
// them by hand. **What is in them is not listed here**: a third copy of every
// domain's statuses would be one more file to edit when a domain is added, and one
// more place for the vocabulary to drift. `src/api/library.test.ts` pins the client's
// arrays against these enums, and `backend/tests/test_domain.py` pins the enums
// against the registry, so the chain runs registry -> enum -> OpenAPI -> client with
// no hand-maintained list in the middle.
for (const name of ["EntryStatus", "EntryFormat", "ItemTypeName"]) {
  if (!components[name]?.enum?.length)
    throw new Error(`OpenAPI schema ${name} publishes no values`);
}

console.log("Frontend library types match the checked OpenAPI surface.");
