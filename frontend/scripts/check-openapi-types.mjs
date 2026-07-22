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
    "score_provisional",
  ],
  ItemResponse: ["id", "type", "title", "sort_author", "cover_path"],
  FacetsResponse: ["status_counts"],
};

for (const [name, properties] of Object.entries(expected)) {
  const actual = components[name]?.properties;
  if (!actual) throw new Error(`OpenAPI schema ${name} is missing`);
  for (const property of properties) {
    if (!(property in actual))
      throw new Error(`OpenAPI schema ${name}.${property} is missing`);
  }
}

const statuses = components.EntryStatus?.enum ?? [];
for (const status of [
  "unsorted",
  "read",
  "reading",
  "to_read",
  "wishlist",
  "dropped",
]) {
  if (!statuses.includes(status))
    throw new Error(`OpenAPI EntryStatus is missing ${status}`);
}

console.log("Frontend library types match the checked OpenAPI surface.");
