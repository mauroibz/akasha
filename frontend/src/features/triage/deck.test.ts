import { describe, expect, it } from "vitest";

import type { ItemType, LibraryEntry } from "@/api/library";
import {
  deckQueue,
  draftFor,
  filingChanges,
  originalTargetFor,
  undoChanges,
} from "./deck";

function entry(id: number, overrides: Partial<LibraryEntry> = {}) {
  return {
    id,
    item_id: id,
    status: "unsorted",
    score: null,
    notes: null,
    date_added: "2026-01-01",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: null,
    score_provisional: false,
    suggested_status: null,
    shelves: [],
    formats: [],
    item: {
      id,
      type: "book",
      title: `Book ${id}`,
      subtitle: null,
      year: null,
      creator: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    ...overrides,
  } as LibraryEntry;
}

const types = [
  {
    id: "book",
    default_status: "read",
    statuses: [
      { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
      { value: "read", label: "Read", choosable: true, hotkey: "r" },
      { value: "to_read", label: "To read", choosable: true, hotkey: "t" },
    ],
  },
] as unknown as ItemType[];

describe("the deck", () => {
  it("leaves out filed and passed cards, keeping the inbox's order", () => {
    const rows = [entry(1), entry(2), entry(3), entry(4)];
    expect(
      deckQueue(rows, new Set([2]), new Set([1])).map((row) => row.id),
    ).toEqual([3, 4]);
  });

  it("targets a draft, else the suggestion, else the domain default", () => {
    expect(originalTargetFor(entry(1), types)).toBe("read");
    expect(
      originalTargetFor(entry(1, { suggested_status: "to_read" }), types),
    ).toBe("to_read");
    expect(
      draftFor(entry(1), types, new Map([[1, "to_read" as const]])).status,
    ).toBe("to_read");
  });

  it("files the status alone when nothing else was touched", () => {
    const row = entry(1, { score: 6, score_provisional: true });
    const draft = draftFor(row, types, new Map());
    // An untouched provisional score is not sent, so it stays provisional.
    expect(filingChanges(row, draft)).toEqual({ status: "read" });
  });

  it("files a touched score and changed shelves in the same request", () => {
    const row = entry(1, { shelves: [{ id: 3, name: "A", slug: "a" }] });
    const draft = {
      ...draftFor(row, types, new Map()),
      score: 9,
      scoreTouched: true,
      shelfIds: [3, 5],
    };
    expect(filingChanges(row, draft)).toEqual({
      status: "read",
      score: 9,
      shelf_ids: [3, 5],
    });
  });

  it("undoes exactly what filing changed", () => {
    const row = entry(1, {
      score: 4,
      shelves: [{ id: 3, name: "A", slug: "a" }],
    });
    expect(
      undoChanges(row, { status: "read", score: 9, shelf_ids: [3, 5] }),
    ).toEqual({ status: "unsorted", score: 4, shelf_ids: [3] });
    expect(undoChanges(row, { status: "read" })).toEqual({
      status: "unsorted",
    });
  });

  it("an undo puts a provisional score back as provisional (Sprint 109)", () => {
    const row = entry(1, { score: 6, score_provisional: true });
    expect(undoChanges(row, { status: "read", score: 9 })).toEqual({
      status: "unsorted",
      score: 6,
      score_provisional: true,
    });
  });
});
