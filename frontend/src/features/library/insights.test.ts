import { describe, expect, it } from "vitest";

import {
  keyLead,
  magnitude,
  orderKeys,
  orderRows,
  quietSummary,
} from "@/features/library/insights";
import type { InsightRow } from "@/api/library";

function row(
  key: string,
  count: number,
  rated: number,
  mean: number | null,
): InsightRow {
  return {
    key,
    label: key,
    count,
    rated_count: rated,
    mean_score: mean,
    score_spread: null,
  };
}

const rows = [
  row("cortazar", 7, 6, 8.8),
  row("le guin", 5, 5, 9.2),
  row("calvino", 3, 3, 7.7),
  row("wolfe", 2, 1, 5.0),
  row("schweblin", 2, 0, null),
];

describe("orderRows", () => {
  it("places every row under the count order, leader first", () => {
    const { placed, unplaced } = orderRows(rows, "count", 2);
    expect(placed.map((r) => r.key)).toEqual([
      "cortazar",
      "le guin",
      "calvino",
      "schweblin",
      "wolfe",
    ]);
    // Nothing is unplaceable by how many you hold: a count is always a count.
    expect(unplaced).toEqual([]);
  });

  it("sets aside what the score order cannot place, rather than dropping it", () => {
    const { placed, unplaced } = orderRows(rows, "score", 2);
    expect(placed.map((r) => r.key)).toEqual([
      "le guin",
      "cortazar",
      "calvino",
    ]);
    expect(unplaced.map((r) => r.key)).toEqual(["schweblin", "wolfe"]);
  });

  it("honours a lowered threshold", () => {
    const { placed } = orderRows(rows, "score", 1);
    expect(placed.map((r) => r.key)).toEqual([
      "le guin",
      "cortazar",
      "calvino",
      "wolfe",
    ]);
  });

  it("breaks a tie the way the server does, on the normalized key", () => {
    const tied = [row("b", 2, 2, 8), row("a", 2, 2, 8), row("c", 2, 2, 8)];
    expect(orderRows(tied, "count", 2).placed.map((r) => r.key)).toEqual([
      "a",
      "b",
      "c",
    ]);
    expect(orderRows(tied, "score", 2).placed.map((r) => r.key)).toEqual([
      "a",
      "b",
      "c",
    ]);
  });
});

describe("keyLead", () => {
  it("is zero for a key with fewer than three values held more than once", () => {
    // Two rows is a fact, not a ranking, however lopsided it is.
    expect(keyLead([row("es", 31, 0, null), row("en", 16, 0, null)])).toBe(0);
    expect(keyLead([])).toBe(0);
  });

  it("is zero when every value appears exactly once", () => {
    const ones = ["a", "b", "c", "d"].map((key) => row(key, 1, 0, null));
    expect(keyLead(ones)).toBe(0);
  });

  it("measures the leader against the middle of its own ranking", () => {
    // 7, 5, 3, 2, 2, 2: the middle of the six is 2, so the leader is 3.5x it.
    const deep = [7, 5, 3, 2, 2, 2].map((count, i) =>
      row(`d${i}`, count, 0, null),
    );
    expect(keyLead(deep)).toBe(3.5);

    // A shallower ranking: the median of 4, 3, 2 is 3.
    const shallow = [4, 3, 2].map((count, i) => row(`s${i}`, count, 0, null));
    expect(keyLead(shallow)).toBeCloseTo(1.333, 3);

    // A ranking with no leader at all scores 1 -- still a ranking, just a flat
    // one, and it keeps its card behind everything with more to say.
    const flat = [4, 4, 3].map((count, i) => row(`f${i}`, count, 0, null));
    expect(keyLead(flat)).toBe(1);
  });

  it("ignores the long tail of ones every key in a personal library has", () => {
    const deep = [6, 3, 2].map((count, i) => row(`d${i}`, count, 0, null));
    const tail = Array.from({ length: 40 }, (_, i) => row(`t${i}`, 1, 0, null));
    expect(keyLead([...deep, ...tail])).toBe(keyLead(deep));
  });
});

describe("orderKeys", () => {
  const key = (name: string, counts: number[]) => ({
    name,
    rows: counts.map((count, i) => row(`${name}-${i}`, count, 0, null)),
  });

  it("cards the keys that rank and sets the rest aside, best first", () => {
    const keys = [
      key("language", [31, 16]),
      key("publisher", [4, 3, 2]),
      key("creators", [7, 5, 3, 2, 2, 2]),
    ];
    const { carded, quiet } = orderKeys(keys, (entry) => entry.rows);
    expect(carded.map((entry) => entry.name)).toEqual([
      "creators",
      "publisher",
    ]);
    expect(quiet.map((entry) => entry.name)).toEqual(["language"]);
  });

  it("keeps the domain's own order between equally interesting keys", () => {
    const keys = [key("first", [4, 3, 2]), key("second", [8, 6, 4])];
    const { carded } = orderKeys(keys, (entry) => entry.rows);
    expect(carded.map((entry) => entry.name)).toEqual(["first", "second"]);
  });
});

describe("quietSummary", () => {
  it("states a two-value key in full, because that is all of it", () => {
    expect(
      quietSummary([row("Spanish", 31, 0, null), row("English", 16, 0, null)]),
    ).toBe("Spanish 31, English 16");
  });

  it("says so when everything appears once, rather than listing three", () => {
    const ones = ["a", "b", "c"].map((k) => row(k, 1, 0, null));
    expect(quietSummary(ones)).toBe("3 values, each appearing once");
  });

  it("has an honest sentence for a key with nothing in it", () => {
    expect(quietSummary([])).toBe("nothing recorded yet");
  });
});

describe("magnitude", () => {
  it("is a share of the leader, not of the whole", () => {
    expect(magnitude(7, 7)).toBe(1);
    expect(magnitude(3, 7)).toBe(0.429);
    expect(magnitude(2, 7)).toBe(0.286);
  });

  it("survives an empty ranking rather than dividing by zero", () => {
    expect(magnitude(0, 0)).toBe(0);
  });
});
