import { describe, expect, it } from "vitest";

import { scoreBand, scoreChipClass, scoreFillClass } from "@/lib/score";

describe("scoreChipClass", () => {
  it("fills a scored chip with its band colour and knocks the numeral out", () => {
    // The chip is the DEC-026 ramp as ground rather than as ink, which is the
    // treatment the open picker already used for its selected segment.
    expect(scoreChipClass(8)).toBe(scoreFillClass.high);
    expect(scoreChipClass(8)).toContain("bg-score-high");
    expect(scoreChipClass(8)).toContain("text-background");
  });

  it("keeps the DEC-026 band boundaries at 3/4, 6/7 and 8/9", () => {
    // Asserted through the chip rather than only through `scoreBand`, because
    // the chip is now what the reader sees on all three surfaces.
    expect(scoreChipClass(3)).toBe(scoreFillClass.low);
    expect(scoreChipClass(4)).toBe(scoreFillClass.mid);
    expect(scoreChipClass(6)).toBe(scoreFillClass.mid);
    expect(scoreChipClass(7)).toBe(scoreFillClass.high);
    expect(scoreChipClass(8)).toBe(scoreFillClass.high);
    expect(scoreChipClass(9)).toBe(scoreFillClass.top);
    expect(scoreChipClass(1)).toBe(scoreFillClass.low);
    expect(scoreChipClass(10)).toBe(scoreFillClass.top);
  });

  it("leaves an unscored entry as muted text with no fill", () => {
    // Only a real score fills. An unscored entry is an absence, not a band.
    expect(scoreChipClass(null)).toBe("text-muted-foreground");
    expect(scoreChipClass(null)).not.toContain("bg-score");
  });

  it("agrees with scoreBand for every score", () => {
    for (let score = 1; score <= 10; score += 1) {
      expect(scoreChipClass(score)).toBe(scoreFillClass[scoreBand(score)]);
    }
  });
});
