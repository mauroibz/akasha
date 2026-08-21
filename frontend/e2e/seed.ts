import type { Page } from "@playwright/test";

/**
 * The deterministic library fixture every large-list test runs against.
 *
 * Lives here rather than in one spec because the accessibility suite, the
 * virtualization bounds and the motion samples all need the same shape, and
 * three near-copies of it would drift.
 */

export const pixelCover =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

const longTitle =
  "A Ludicrously Long Title About The Consequences Of Unbounded Metadata In Virtualized Grids And Their Discontents";
const longAuthor =
  "Vandermeer-Vandermeer de la Fuente y Castellanos de Arag\u00f3n, Mar\u00eda Purificaci\u00f3n";

export function entry(id: number) {
  return {
    id,
    item_id: id,
    status: "read",
    score: (id % 10) + 1,
    notes: null,
    date_added: "2026-07-22T00:00:00Z",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    score_provisional: id % 3 === 0,
    suggested_status: null,
    item: {
      id,
      type: "book",
      // The first two entries carry deliberately hostile metadata so layout
      // assertions cover long titles/creators, and every other entry carries a
      // real cover so both populated and empty covers are exercised.
      title:
        id <= 2
          ? `${longTitle} ${String(id).padStart(4, "0")}`
          : `Seeded book ${String(id).padStart(4, "0")}`,
      subtitle: null,
      year: 1900 + (id % 126),
      creator: id <= 2 ? longAuthor : `Author ${id % 200}`,
      cover_url: id % 2 === 0 ? pixelCover : null,
      cover_path: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    shelves: [],
    formats: [],
  };
}

export async function seedLibrary(page: Page, count = 5000) {
  const items = Array.from({ length: count }, (_, index) => entry(index + 1));
  await page.route("**/api/entries?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items,
        next_cursor: null,
        total: count,
        facets: {
          status_counts: { read: count, unsorted: 27 },
          status_counts_by_type: {},
          format_counts: {},
        },
      }),
    });
  });
}

/** The book field spec, as `GET /api/item-types` serves it (DEC-052 seam 3). */
export const bookItemType = {
  id: "book",
  label: "Book",
  fields: [
    { name: "creators", label: "Creators", type: "text", multiplicity: "many" },
    {
      name: "publisher",
      label: "Publisher",
      type: "text",
      multiplicity: "one",
    },
    { name: "language", label: "Language", type: "text", multiplicity: "one" },
    {
      name: "page_count",
      label: "Page count",
      type: "number",
      multiplicity: "one",
      minimum: 1,
      maximum: 100000,
    },
    {
      name: "description",
      label: "Description",
      type: "long_text",
      multiplicity: "one",
    },
    { name: "subjects", label: "Subjects", type: "text", multiplicity: "many" },
    { name: "series", label: "Series", type: "text", multiplicity: "one" },
    {
      name: "original_year",
      label: "Original publication year",
      type: "number",
      multiplicity: "one",
      minimum: 0,
      maximum: 9999,
    },
  ],
  statuses: [
    { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
    { value: "read", label: "Read", choosable: true, hotkey: "r" },
    { value: "reading", label: "Reading", choosable: true, hotkey: "g" },
    { value: "to_read", label: "To read", choosable: true, hotkey: "t" },
    { value: "wishlist", label: "Wishlist", choosable: true, hotkey: "w" },
    { value: "dropped", label: "Dropped", choosable: true, hotkey: "d" },
  ],
  default_status: "read",
  entry_fields: ["date_started", "date_finished", "reread_count"],
  formats: [
    { value: "physical", label: "Physical" },
    { value: "borrowed", label: "Borrowed" },
    { value: "digital", label: "Digital" },
  ],
  entry_panel_label: "Your reading data",
};

/** The album domain, whose entries record possession rather than reading. */
export const albumItemType = {
  id: "album",
  label: "Album",
  fields: [
    { name: "creators", label: "Artists", type: "text", multiplicity: "many" },
    { name: "label", label: "Label", type: "text", multiplicity: "one" },
    {
      name: "tracklist",
      label: "Tracklist",
      type: "rows",
      multiplicity: "many",
      columns: [
        { name: "position", label: "#", type: "number" },
        { name: "title", label: "Title", type: "text" },
        { name: "length_ms", label: "Length", type: "duration" },
      ],
    },
  ],
  statuses: [
    { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
    { value: "wishlist", label: "Wishlist", choosable: true, hotkey: "w" },
    { value: "pending", label: "On the way", choosable: true, hotkey: "p" },
    { value: "owned", label: "Owned", choosable: true, hotkey: "o" },
  ],
  default_status: "owned",
  entry_fields: [],
  formats: [
    { value: "vinyl", label: "Vinyl" },
    { value: "cd", label: "CD" },
    { value: "digital", label: "Digital" },
  ],
  entry_panel_label: "Your copy",
};

/** Every screen that renders metadata needs the spec that describes it. */
export async function stubItemTypes(page: Page, types = [bookItemType]) {
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: types }),
  );
}

/**
 * The importer registry the folded import screen renders from.
 *
 * Shared rather than copied per spec: the screen renders whatever a connector
 * declares (DEC-080), so every spec that opens `/import` — including the ones
 * that only want the triage tab behind it — needs the same declaration, and four
 * near-copies would drift the first time a field is added.
 */
export async function stubImporters(page: Page) {
  await page.route("**/api/importers", (route) =>
    route.fulfill({
      json: [
        {
          id: "goodreads",
          label: "Goodreads",
          item_type: "book",
          input: {
            kind: "upload",
            label: "Goodreads CSV",
            field: "file",
            accept: ".csv,text/csv",
            placeholder: null,
            help: null,
            guide: [
              "Open goodreads.com/review/import on desktop web.",
              "Press Export Library and download the file.",
            ],
            empty_state:
              "Drop goodreads_library_export.csv here, or choose a file.",
            help_url: "https://www.goodreads.com/review/import",
            browsable: false,
            incremental: false,
            accepts_files: false,
            max_bytes: null,
            max_files: null,
            alternate: null,
          },
        },
        {
          id: "calibre",
          label: "Calibre",
          item_type: "book",
          input: {
            kind: "directory",
            label: "Calibre folder",
            field: "files",
            accept: null,
            placeholder: null,
            help: "Akasha reads the library you choose and copies only metadata and covers.",
            guide: [
              "Choose your Calibre library folder — the one with metadata.db.",
            ],
            empty_state: "Choose your Calibre library folder.",
            help_url: "https://manual.calibre-ebook.com/gui.html",
            browsable: false,
            incremental: true,
            accepts_files: true,
            max_bytes: 256 * 1024 * 1024,
            max_files: 10000,
            alternate: {
              kind: "path",
              label: "Calibre library path",
              field: "library_path",
              accept: null,
              placeholder: "Library",
              help: "Or read a library the server can already see.",
              guide: [],
              empty_state:
                "No folders here. Mount your Calibre library and reload.",
              help_url: null,
              browsable: true,
              incremental: false,
              accepts_files: false,
              max_bytes: null,
              max_files: null,
              alternate: null,
            },
          },
        },
      ],
    }),
  );
  await page.route("**/api/import/calibre/browse**", (route) => {
    const path = new URL(route.request().url()).searchParams.get("path") ?? "";
    route.fulfill({
      json:
        path === ""
          ? {
              path: "",
              parent: null,
              directories: ["Comics", "Fiction"],
              importable: false,
            }
          : { path, parent: "", directories: [], importable: true },
    });
  });
}
