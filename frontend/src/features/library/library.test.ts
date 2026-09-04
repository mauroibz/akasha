import { describe, expect, it, test } from "vitest";

import type { LibraryEntry, LibraryFilters } from "@/api/library";
import {
  defaultLibraryFilters,
  gridColumnCount,
  gridLayout,
  hasRememberedFilters,
  isEditableTarget,
  libraryFiltersPreferenceKey,
  libraryMotionKey,
  mergeUniqueEntries,
  readLibraryFiltersPreference,
  readViewPreference,
  rememberLibraryFilters,
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
  // Container widths observed in Chromium at the supported viewports.
  expect(gridColumnCount(320)).toBe(1);
  expect(gridColumnCount(689)).toBe(2);
  expect(gridColumnCount(1201)).toBe(4);
  // Degenerate widths (unmeasured container, server render) stay single-column.
  expect(gridColumnCount(0)).toBe(1);
  expect(gridColumnCount(-100)).toBe(1);
  expect(gridColumnCount(Number.NaN)).toBe(1);
  expect(gridColumnCount(10_000)).toBe(gridLayout.maxColumns);
  // Every column keeps at least the minimum card width.
  for (const width of [320, 500, 689, 900, 1201, 1600]) {
    const columns = gridColumnCount(width);
    const cardWidth =
      (width - gridLayout.paddingX - (columns - 1) * gridLayout.gap) / columns;
    if (columns > 1)
      expect(cardWidth).toBeGreaterThanOrEqual(gridLayout.cardMinWidth);
  }
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
