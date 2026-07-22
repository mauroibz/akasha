import { expect, test } from "vitest";

import type { LibraryEntry } from "@/api/library";
import {
  defaultLibraryFilters,
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

test("default server filters omit status so the API excludes inbox", () => {
  expect(defaultLibraryFilters.statuses).toEqual([]);
  expect(defaultLibraryFilters.sort).toBe("date_added");
});
