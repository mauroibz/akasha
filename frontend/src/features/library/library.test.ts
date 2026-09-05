import { describe, expect, it, test } from "vitest";

import type { LibraryEntry, LibraryFilters } from "@/api/library";
import {
  containerWidthFor,
  defaultLibraryFilters,
  gridColumnCount,
  gridLayout,
  gridRowHeight,
  hasRememberedFilters,
  isEditableTarget,
  libraryFiltersPreferenceKey,
  libraryMotionKey,
  mergeUniqueEntries,
  readLibraryFiltersPreference,
  readViewPreference,
  rememberLibraryFilters,
  tableRowHeight,
} from "./library";

const entry = (id: number) => ({ id }) as LibraryEntry;

test("deduplicates overlapping opaque cursor pages while keeping order", () => {
  expect(
    mergeUniqueEntries([
      [entry(1), entry(2)],
      [entry(2), entry(3)],
    ]),
  ).toEqual([entry(1), entry(2), entry(3)]);
});

test("defaults to grid and restores only valid persisted preferences", () => {
  localStorage.clear();
  expect(readViewPreference()).toBe("grid");
  localStorage.setItem("akasha.library.view", "table");
  expect(readViewPreference()).toBe("table");
  localStorage.setItem("akasha.library.view", "other");
  expect(readViewPreference()).toBe("grid");
});

test("grid columns follow the measured width and never starve a card", () => {
  // Sprint 072's wall geometry (DEC-139): a ~190px minimum card, a pinned
  // 300px cover and a text block under it. Assertion widths are the container
  // the page actually presents to the wall — main's side padding comes out of
  // the viewport — which is what `containerWidthFor` derives and what
  // VirtualLibrary measures at runtime. The three viewports below are the
  // acceptance trio (AC3): one column on a phone, five+ at 1440, six+ at 2560.
  expect(gridColumnCount(containerWidthFor(390))).toBe(1);
  expect(gridColumnCount(containerWidthFor(1440))).toBeGreaterThanOrEqual(5);
  expect(gridColumnCount(containerWidthFor(2560))).toBeGreaterThanOrEqual(6);
  // Pin the exact answers so a constant change gets reviewed, not discovered:
  // 1440 presents 1376px (main - px-8). 2560 clamps to the 1600px container,
  // so it presents 1536px — and DEC-139's six-column cap holds there.
  expect(gridColumnCount(1376)).toBe(6);
  expect(gridColumnCount(1536)).toBe(gridLayout.maxColumns);
  expect(gridLayout.maxColumns).toBe(6);
  // Degenerate widths (unmeasured container, server render) stay single-column.
  expect(gridColumnCount(0)).toBe(1);
  expect(gridColumnCount(-100)).toBe(1);
  expect(gridColumnCount(Number.NaN)).toBe(1);
  // An absurd window still mounts a finite wall.
  expect(gridColumnCount(10_000)).toBe(gridLayout.maxColumns);
  // Every column keeps at least the minimum card width.
  for (const width of [320, 500, 689, 900, 1201, 1408, 1600, 1848, 2400]) {
    const columns = gridColumnCount(width);
    const cardWidth =
      (width - gridLayout.paddingX - (columns - 1) * gridLayout.gap) / columns;
    if (columns > 1)
      expect(cardWidth).toBeGreaterThanOrEqual(gridLayout.cardMinWidth);
  }
});

test("the grid card is cover-first and its row height is one band (DEC-023)", () => {
  expect(gridLayout.cardMinWidth).toBe(190);
  expect(gridLayout.coverHeight).toBe(300);
  // Card = pinned cover + text block; the row band adds the gap.
  expect(gridLayout.cardHeight).toBe(
    gridLayout.coverHeight + gridLayout.textHeight,
  );
  expect(gridRowHeight).toBe(gridLayout.cardHeight + gridLayout.gap);
});

test("the second density is a genuinely dense fixed-height row", () => {
  expect(tableRowHeight).toBe(52);
  expect(Math.floor(900 / tableRowHeight)).toBeGreaterThanOrEqual(16);
});

test("global shortcuts stay disabled while a control owns the keystroke", () => {
  const make = (html: string) => {
    const host = document.createElement("div");
    host.innerHTML = html;
    return host.firstElementChild as HTMLElement;
  };
  // Native controls, as before.
  expect(isEditableTarget(make("<input />"))).toBe(true);
  expect(isEditableTarget(make("<textarea></textarea>"))).toBe(true);
  expect(isEditableTarget(make("<select></select>"))).toBe(true);
  // `contenteditable` is covered by the implementation but not asserted here:
  // jsdom does not implement HTMLElement.isContentEditable, so the assertion
  // would test jsdom rather than this guard.
  // Radix renders a Select trigger as a button and portals both the dialog and
  // the listbox to document.body. Guarding only on tagName would let `7` set a
  // score while a status dropdown has focus, and guarding only on a dialog
  // ancestor would miss the portalled listbox entirely.
  expect(isEditableTarget(make('<button role="combobox"></button>'))).toBe(
    true,
  );
  expect(
    isEditableTarget(make('<div role="listbox"><span></span></div>')),
  ).toBe(true);
  expect(isEditableTarget(make('<div role="dialog"><button /></div>'))).toBe(
    true,
  );
  expect(
    isEditableTarget(make('<div role="alertdialog"><button /></div>')),
  ).toBe(true);
  // An ordinary row is still fair game for j/k and score digits.
  expect(isEditableTarget(make("<article></article>"))).toBe(false);
  expect(isEditableTarget(null)).toBe(false);
});

test("default server filters omit status so the API excludes inbox", () => {
  expect(defaultLibraryFilters.statuses).toEqual([]);
  expect(defaultLibraryFilters.sort).toBe("date_added");
});

describe("libraryMotionKey", () => {
  const base = defaultLibraryFilters;

  it("is stable across everything that is not a server filter", () => {
    // Loading another page or patching one row's score in the cache produces
    // the same filters object; re-keying on those would crossfade the whole
    // list on every scroll and every inline edit.
    expect(libraryMotionKey(base)).toBe(libraryMotionKey({ ...base }));
  });

  it("changes with sort, order, status, shelf, and query", () => {
    const key = libraryMotionKey(base);
    expect(libraryMotionKey({ ...base, sort: "score" })).not.toBe(key);
    expect(libraryMotionKey({ ...base, order: "asc" })).not.toBe(key);
    expect(libraryMotionKey({ ...base, statuses: ["read"] })).not.toBe(key);
    expect(libraryMotionKey({ ...base, shelves: ["3"] })).not.toBe(key);
    expect(libraryMotionKey({ ...base, query: "borges" })).not.toBe(key);
  });

  it("ignores the order the reader happened to tick the filters in", () => {
    expect(libraryMotionKey({ ...base, statuses: ["read", "reading"] })).toBe(
      libraryMotionKey({ ...base, statuses: ["reading", "read"] }),
    );
    expect(libraryMotionKey({ ...base, shelves: ["2", "9"] })).toBe(
      libraryMotionKey({ ...base, shelves: ["9", "2"] }),
    );
  });
});

describe("the remembered library filters (Sprint 067)", () => {
  it("defaults to empty, and is not confused by a value from an older version", () => {
    localStorage.clear();
    expect(readLibraryFiltersPreference()).toEqual({
      statuses: [],
      shelves: [],
      formats: [],
      query: "",
    });

    localStorage.setItem(libraryFiltersPreferenceKey, "not json");
    expect(readLibraryFiltersPreference()).toEqual({
      statuses: [],
      shelves: [],
      formats: [],
      query: "",
    });

    localStorage.setItem(libraryFiltersPreferenceKey, JSON.stringify(42));
    expect(readLibraryFiltersPreference()).toEqual({
      statuses: [],
      shelves: [],
      formats: [],
      query: "",
    });
  });

  it("round-trips what the library page last had set, and only that", () => {
    localStorage.clear();
    const filters: LibraryFilters = {
      ...defaultLibraryFilters,
      statuses: ["read"],
      shelves: ["fiction"],
      formats: ["physical"],
      query: "borges",
      types: ["book"],
      key: "creators",
      value: "borges",
    };
    rememberLibraryFilters(filters);
    expect(readLibraryFiltersPreference()).toEqual({
      statuses: ["read"],
      shelves: ["fiction"],
      formats: ["physical"],
      query: "borges",
    });
  });

  it("says whether any remembered filter would actually narrow a ranking", () => {
    expect(
      hasRememberedFilters({
        statuses: [],
        shelves: [],
        formats: [],
        query: "  ",
      }),
    ).toBe(false);
    expect(
      hasRememberedFilters({
        statuses: ["read"],
        shelves: [],
        formats: [],
        query: "",
      }),
    ).toBe(true);
  });
});
