import { describe, expect, it } from "vitest";

import {
  slotsFor,
  suggestedCounts,
  yearPassed,
  goalSentence,
} from "@/features/goals/goals";
import type { Segment } from "@/features/insights/prose";

const text = (segments: Segment[]) =>
  segments.map((segment) => segment.text).join("");
const october21 = new Date(2026, 9, 21);
const months = [2, 1, 3, 2, 0, 2, 4, 1, 1, 1, 0, 0];

describe("the goal's sentence", () => {
  const progress = { months, total: 17, year: 2026 };

  it("says where this month stands, gently", () => {
    expect(
      text(goalSentence({ count: 2, period: "month" }, progress, october21)),
    ).toBe("Two a month, at your own pace. October has one so far.");
    const full = { ...progress, months: [...months.slice(0, 9), 3, 0, 0] };
    expect(
      text(goalSentence({ count: 2, period: "month" }, full, october21)),
    ).toBe("Two a month, at your own pace. October has three already.");
    const empty = { ...progress, months: [...months.slice(0, 9), 0, 0, 0] };
    expect(
      text(goalSentence({ count: 2, period: "month" }, empty, october21)),
    ).toBe("Two a month, at your own pace. October is still open.");
  });

  it("speaks of the year for a yearly goal, and in the past for a past year", () => {
    expect(
      text(goalSentence({ count: 30, period: "year" }, progress, october21)),
    ).toBe("30 this year, at your own pace. 17 so far.");
    expect(
      text(
        goalSentence(
          { count: 2, period: "month" },
          { ...progress, year: 2025 },
          october21,
        ),
      ),
    ).toBe("You finished 17 in 2025, against two a month.");
  });
});

describe("the goal in the Diary (Sprint 127)", () => {
  it("suggests three numbers above what is already done, each in words", () => {
    expect(suggestedCounts(2)).toEqual([
      { count: 6, words: "one every two months" },
      { count: 12, words: "one a month" },
      { count: 24, words: "two a month" },
    ]);
    expect(suggestedCounts(14).map((pick) => pick.count)).toEqual([24, 36, 52]);
  });

  it("draws a slot for each thing aimed at, filled in order, and a bar above 24", () => {
    const e = (id: number, day: string) => ({ id, date_finished: day });
    const slots = slotsFor(12, [e(2, "2026-03-04"), e(1, "2026-02-03")]);
    expect(slots?.map((slot) => slot.entry?.id ?? null)).toEqual([
      1,
      2,
      null,
      null,
      null,
      null,
      null,
      null,
      null,
      null,
      null,
      null,
    ]);
    expect(slots?.[2].next).toBe(true);
    expect(slotsFor(30, [])).toBeNull();
    // Beyond the goal, every finish still has a place.
    expect(slotsFor(1, [e(1, "2026-01-01"), e(2, "2026-02-01")])).toHaveLength(
      2,
    );
  });

  it("knows how much of the year has passed", () => {
    expect(yearPassed(2026, new Date(2026, 6, 2))).toBeCloseTo(0.5, 1);
    expect(yearPassed(2025, new Date(2026, 6, 2))).toBe(1);
  });
});
