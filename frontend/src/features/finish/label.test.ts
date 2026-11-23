import { describe, expect, it } from "vitest";

import type { ItemType } from "@/api/library";

import { finishAction, finishActionFor } from "./label";

const types = [
  {
    id: "book",
    statuses: [
      { value: "read", label: "Read", finished: true },
      { value: "to_read", label: "To read", planned: true },
    ],
  },
  {
    id: "movie",
    statuses: [{ value: "watched", label: "Watched", finished: true }],
  },
  { id: "album", statuses: [{ value: "owned", label: "Owned" }] },
] as unknown as ItemType[];

describe("finishAction", () => {
  it("names the action in the domain's own word", () => {
    expect(finishAction("book", types)).toBe("Mark as read");
    expect(finishAction("movie", types)).toBe("Mark as watched");
    expect(finishActionFor("Paris, Texas", "movie", types)).toBe(
      "Mark Paris, Texas as watched",
    );
  });

  it("falls back where a domain declares no finished status", () => {
    expect(finishAction("album", types)).toBe("Mark finished");
    expect(finishActionFor("Kind of Blue", "album", undefined)).toBe(
      "Mark Kind of Blue finished",
    );
  });
});
