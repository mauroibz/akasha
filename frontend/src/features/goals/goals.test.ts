import { describe, expect, it } from "vitest";

import {
  calendarPlaces,
  columnCap,
  goalSentence,
} from "@/features/goals/goals";
import type { Segment } from "@/features/insights/prose";

const text = (segments: Segment[]) =>
  segments.map((segment) => segment.text).join("");
const october21 = new Date(2026, 9, 21);
const months = [2, 1, 3, 2, 0, 2, 4, 1, 1, 1, 0, 0];

describe("the calendar of lights", () => {
  it("lights one place per finished entry, beyond the goal too", () => {
    const calendar = calendarPlaces(
      months,
      { count: 2, period: "month" },
      2026,
      october21,
    );
    expect(calendar[0].places).toEqual(["lit", "lit"]);
    expect(calendar[1].places).toEqual(["lit", "open"]);
    expect(calendar[2].places).toEqual(["lit", "lit", "lit"]);
    expect(calendar[4].places).toEqual(["open", "open"]);
  });

  it("marks this month as now and later months as ahead, never as missed", () => {
    const calendar = calendarPlaces(
      months,
      { count: 2, period: "month" },
      2026,
      october21,
    );
    expect(calendar[9]).toMatchObject({
      current: true,
      places: ["lit", "now"],
    });
    expect(calendar[10].places).toEqual(["ahead", "ahead"]);
    expect(calendar.flatMap((month) => month.places)).not.toContain("missed");
  });

  it("draws a busy month to a cap and says the rest", () => {
    const busy = [9, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    const [january] = calendarPlaces(
      busy,
      { count: 2, period: "month" },
      2026,
      october21,
    );
    expect(january.places).toHaveLength(columnCap);
    expect(january.more).toBe(3);
  });

  it("holds only what was finished under a yearly goal, and has no now in a past year", () => {
    const calendar = calendarPlaces(
      months,
      { count: 24, period: "year" },
      2025,
      october21,
    );
    expect(calendar[4].places).toEqual([]);
    expect(calendar[9]).toMatchObject({ current: false, places: ["lit"] });
  });
});

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
