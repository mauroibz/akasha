import { describe, expect, it } from "vitest";

import type { ItemType, LibraryEntry } from "@/api/library";

import { askStill, scoreArticle, stillReason, statusWith } from "./rescore";

const book = {
  id: "book",
  statuses: [
    { value: "read", label: "Read", choosable: true, finished: true },
    { value: "reading", label: "Reading", choosable: true, in_progress: true },
    { value: "to_read", label: "To read", choosable: true, planned: true },
  ],
} as unknown as ItemType;
const movie = {
  id: "movie",
  statuses: [
    { value: "watched", label: "Watched", choosable: true, finished: true },
    { value: "watchlist", label: "Watchlist", choosable: true, planned: true },
  ],
} as unknown as ItemType;

function entry(overrides: Partial<LibraryEntry> = {}): LibraryEntry {
  return {
    id: 1,
    status: "reading",
    score: 8,
    reread_count: 0,
    item: { type: "book" },
    ...overrides,
  } as LibraryEntry;
}

describe("Still an 8? (Sprint 115)", () => {
  it("is asked when a scored entry moves into its finished status", () => {
    const types = [book, movie];
    expect(askStill(entry(), entry({ status: "read" }), types)).toBe(true);
    // Already finished, no score yet, a new score in the same save: not asked.
    expect(
      askStill(entry({ status: "read" }), entry({ status: "read" }), types),
    ).toBe(false);
    expect(
      askStill(
        entry({ score: null }),
        entry({ status: "read", score: null }),
        types,
      ),
    ).toBe(false);
    expect(askStill(entry(), entry({ status: "read", score: 9 }), types)).toBe(
      false,
    );
    expect(askStill(entry(), entry({ status: "to_read" }), types)).toBe(false);
  });

  it("names the domain's own statuses by what they mean", () => {
    expect(statusWith("book", [book], "finished")).toBe("read");
    expect(statusWith("book", [book], "in_progress")).toBe("reading");
    expect(statusWith("movie", [movie], "in_progress")).toBeNull();
  });

  it("says why: a reread when the entry has been started again, else time", () => {
    expect(stillReason(entry({ reread_count: 1 }))).toBe("reread");
    expect(stillReason(entry())).toBe("time");
  });

  it("reads aloud: an 8, a 9", () => {
    expect(scoreArticle(8)).toBe("an 8");
    expect(scoreArticle(9)).toBe("a 9");
    expect(scoreArticle(10)).toBe("a 10");
  });
});
