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

// The union of every domain's vocabulary, which is what a filter spans. Which of
// these a given entry may hold is the domain's business and is checked per item type
// on the server (seam 5b) — this only pins the surface a client can send.
const statuses = components.EntryStatus?.enum ?? [];
for (const status of [
  "unsorted",
  "read",
  "reading",
  "to_read",
  "wishlist",
  "dropped",
  "pending",
  "owned",
]) {
  if (!statuses.includes(status))
    throw new Error(`OpenAPI EntryStatus is missing ${status}`);
}

const formats = components.EntryFormat?.enum ?? [];
for (const format of ["physical", "borrowed", "digital", "vinyl", "cd"]) {
  if (!formats.includes(format))
    throw new Error(`OpenAPI EntryFormat is missing ${format}`);
}

console.log("Frontend library types match the checked OpenAPI surface.");
