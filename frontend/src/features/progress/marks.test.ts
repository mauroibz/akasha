import { describe, expect, it } from "vitest";

import {
  countMarks,
  drawnMarks,
  fillThrough,
  isMarked,
  partState,
  toggleMark,
  togglePart,
} from "@/features/progress/marks";

const seasons = [
  { part: 1, size: 3 },
  { part: 2, size: 4 },
];

describe("drawnMarks", () => {
  it("uses the stored marks when there are any", () => {
    expect(drawnMarks({ "2": [1] }, 5, seasons)).toEqual({ "2": [1] });
  });

  it("draws an imported count as the first N in outline order", () => {
    expect(drawnMarks(null, 5, seasons)).toEqual({
      "1": [1, 2, 3],
      "2": [1, 2],
    });
  });

  it("draws nothing for no count, and never past the outline", () => {
    expect(drawnMarks(null, null, seasons)).toEqual({});
    expect(drawnMarks(undefined, 0, seasons)).toEqual({});
    expect(drawnMarks(null, 99, seasons)).toEqual({
      "1": [1, 2, 3],
      "2": [1, 2, 3, 4],
    });
  });
});

describe("toggling", () => {
  it("toggles one mark and keeps numbers sorted", () => {
    const once = toggleMark({ "1": [3] }, 1, 1);
    expect(once).toEqual({ "1": [1, 3] });
    expect(toggleMark(once, 1, 3)).toEqual({ "1": [1] });
  });

  it("drops a part left empty", () => {
    expect(toggleMark({ "1": [2] }, 1, 2)).toEqual({});
  });

  it("fills a part, or clears it when it is all marked", () => {
    expect(togglePart({ "1": [2] }, seasons[0])).toEqual({ "1": [1, 2, 3] });
    expect(togglePart({ "1": [1, 2, 3], "2": [1] }, seasons[0])).toEqual({
      "2": [1],
    });
  });

  it("keeps marks outside the outline when a part is filled", () => {
    expect(togglePart({ "1": [9] }, seasons[0])).toEqual({
      "1": [1, 2, 3, 9],
    });
  });
});

describe("fillThrough", () => {
  it("marks everything up to and including the one where you stopped", () => {
    expect(fillThrough(seasons, 2, 2)).toEqual({
      "1": [1, 2, 3],
      "2": [1, 2],
    });
    expect(fillThrough(seasons, 1, 1)).toEqual({ "1": [1] });
  });
});

describe("reading", () => {
  it("counts, asks and describes a part", () => {
    const marks = { "1": [1, 2, 3], "2": [2] };
    expect(countMarks(marks)).toBe(4);
    expect(isMarked(marks, 2, 2)).toBe(true);
    expect(isMarked(marks, 2, 1)).toBe(false);
    expect(partState(marks, seasons[0])).toBe("all");
    expect(partState(marks, seasons[1])).toBe("some");
    expect(partState({}, seasons[1])).toBe("none");
  });
});
