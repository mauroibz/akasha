import { describe, expect, it } from "vitest";

import type { ItemType, LibraryEntry } from "@/api/library";

import { questionsFor } from "./questions";

const book = {
  id: "book",
  statuses: [
    { value: "reading", label: "Reading", in_progress: true },
    { value: "read", label: "Read", finished: true },
    { value: "to_read", label: "To read", planned: true },
  ],
  entry_fields: ["date_started", "date_finished", "reread_count"],
  formats: [{ value: "physical", label: "Physical" }],
} as unknown as ItemType;
const film = {
  ...book,
  id: "movie",
  statuses: [{ value: "watched", label: "Watched", finished: true }],
  entry_fields: ["date_finished", "reread_count"],
  formats: [],
} as unknown as ItemType;

const entry = (changes: Partial<LibraryEntry> = {}, type = "book") =>
  ({
    status: "read",
    date_started: null,
    date_finished: null,
    formats: [],
    location: null,
    unknown_fields: [],
    item: { type },
    ...changes,
  }) as unknown as LibraryEntry;

describe("questionsFor (Sprint 124)", () => {
  it("asks the most useful gap first: the finish, the format, the place, the start", () => {
    expect(questionsFor(entry(), [book])).toEqual([
      "date_finished",
      "formats",
      "location",
      "date_started",
    ]);
  });

  it("asks nothing that is known or that the owner does not remember", () => {
    expect(
      questionsFor(
        entry({
          date_finished: "2026-01-02",
          location: "Hall",
          unknown_fields: ["formats"],
        }),
        [book],
      ),
    ).toEqual(["date_started"]);
  });

  it("asks only what the domain has, and nothing about dates before a start", () => {
    expect(questionsFor(entry({ status: "watched" }, "movie"), [film])).toEqual(
      ["date_finished", "location"],
    );
    expect(questionsFor(entry({ status: "to_read" }), [book])).toEqual([
      "formats",
    ]);
    expect(questionsFor(entry({ status: "reading" }), [book])).toEqual([
      "formats",
      "location",
      "date_started",
    ]);
  });
});
