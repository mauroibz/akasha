import { expect, test } from "vitest";

import type { LibraryEntry } from "@/api/library";
import {
  defaultLibraryFilters,
  gridColumnCount,
  gridLayout,
  mergeUniqueEntries,
  readViewPreference,
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

test("default server filters omit status so the API excludes inbox", () => {
  expect(defaultLibraryFilters.statuses).toEqual([]);
  expect(defaultLibraryFilters.sort).toBe("date_added");
});
