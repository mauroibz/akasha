import { describe, expect, it } from "vitest";

import { howLong, readableDay } from "./house";

describe("the house's dates (Sprint 111)", () => {
  const today = new Date(2026, 9, 23);

  it("says how long something has been out, in the unit that reads naturally", () => {
    expect(howLong("2026-10-23", today)).toBe("since today");
    expect(howLong("2026-10-22", today)).toBe("1 day");
    expect(howLong("2026-10-13", today)).toBe("10 days");
    expect(howLong("2026-09-01", today)).toBe("7 weeks");
    expect(howLong("2026-04-02", today)).toBe("6 months");
    expect(howLong("2024-04-02", today)).toBe("2 years");
  });

  it("reads a stored day as the owner's own calendar day", () => {
    // Parsed as a local date: a UTC parse would print 1 April in Buenos Aires.
    expect(readableDay("2026-04-02")).toMatch(/2/);
    expect(readableDay("2026-04-02")).toMatch(/2026/);
  });
});
