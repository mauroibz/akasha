import { describe, expect, it } from "vitest";

import { orderRows } from "@/features/library/insights";
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
