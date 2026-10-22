import { describe, expect, it } from "vitest";

import type { ItemType, LibraryEntry } from "@/api/library";
import { localDay, passageDates } from "@/features/progress/outline";

const types = [
  { id: "series", entry_fields: ["date_started", "date_finished"] },
  { id: "album", entry_fields: [] },
] as unknown as ItemType[];

const entry = (overrides: Partial<LibraryEntry> = {}, type = "series") =>
  ({
    date_started: null,
    date_finished: null,
    ...overrides,
    item: { type },
  }) as unknown as LibraryEntry;

const today = new Date(2026, 9, 22, 23, 30);

describe("passageDates", () => {
  it("starts an entry on its first light", () => {
    expect(passageDates(entry(), types, 0, 1, 62, today)).toEqual({
      date_started: "2026-10-22",
    });
  });

  it("finishes it on the last light", () => {
    expect(passageDates(entry(), types, 61, 62, 62, today)).toEqual({
      date_finished: "2026-10-22",
    });
  });

  it("does both when one tap lights all of it", () => {
    expect(passageDates(entry(), types, 0, 7, 7, today)).toEqual({
      date_started: "2026-10-22",
      date_finished: "2026-10-22",
    });
  });

  it("never replaces a date already there", () => {
    expect(
      passageDates(
        entry({ date_started: "2020-01-01", date_finished: "2021-01-01" }),
        types,
        0,
        7,
        7,
        today,
      ),
    ).toEqual({});
  });

  it("does nothing between the first and the last, or going down", () => {
    expect(passageDates(entry(), types, 3, 4, 62, today)).toEqual({});
    expect(passageDates(entry(), types, 62, 61, 62, today)).toEqual({});
    expect(passageDates(entry(), types, 1, 0, 62, today)).toEqual({});
  });

  it("fills only dates the domain has", () => {
    expect(passageDates(entry({}, "album"), types, 0, 7, 7, today)).toEqual({});
  });

  it("reads the day in the reader's own time zone", () => {
    expect(localDay(new Date(2026, 0, 5, 0, 10))).toBe("2026-01-05");
  });
});
