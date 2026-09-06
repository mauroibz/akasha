import { describe, expect, it } from "vitest";

import {
  chronologyBuckets,
  computeSuperlatives,
  insightGridSpan,
  keyLead,
  magnitude,
  orderKeys,
  orderRows,
  quietSummary,
  resolveAnsweredKeys,
  weightClass,
} from "@/features/library/insights";
import type { Insight, InsightRow } from "@/api/library";

function row(
  key: string,
  count: number,
  rated: number,
  mean: number | null,
  spread: number | null = null,
  covers: string[] = [],
): InsightRow {
  return {
    key,
    label: key,
    count,
    rated_count: rated,
    mean_score: mean,
    score_spread: spread,
    covers,
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

describe("weightClass", () => {
  it("gives the leading share the heaviest class and a small one the quietest", () => {
    expect(weightClass(30, 30)).toBe("text-base font-semibold tabular-nums");
    expect(weightClass(12, 30)).toBe("text-sm font-medium tabular-nums");
    expect(weightClass(1, 30)).toBe(
      "text-sm text-muted-foreground tabular-nums",
    );
  });

  it("survives a zero ceiling rather than dividing by zero", () => {
    expect(weightClass(0, 0)).toBe(
      "text-sm text-muted-foreground tabular-nums",
    );
  });
});

describe("computeSuperlatives", () => {
  it("names most collected, highest rated and steadiest, drawn from one key", () => {
    const withSpread = [
      row("cortazar", 7, 6, 8.8, 0.9),
      row("le guin", 5, 5, 9.2, 0.3),
      row("calvino", 3, 3, 7.7, 1.2),
    ];
    const superlatives = computeSuperlatives(withSpread, 2);
    expect(superlatives).toEqual([
      { kind: "most_collected", row: withSpread[0] },
      { kind: "highest_rated", row: withSpread[1] },
      { kind: "steadiest", row: withSpread[1] },
    ]);
  });

  it("leaves out highest rated and steadiest when nothing meets minRated", () => {
    const oneRatingEach = [
      row("cortazar", 3, 1, 9.0, null),
      row("le guin", 2, 1, 8.0, null),
    ];
    expect(computeSuperlatives(oneRatingEach, 2)).toEqual([
      { kind: "most_collected", row: oneRatingEach[0] },
    ]);
  });

  it("can name a different row for highest rated than for steadiest", () => {
    // A single rating gives a mean but never a spread (the server needs two), so
    // the best mean and the best spread need not belong to the same row.
    const rows = [
      row("cortazar", 3, 2, 9.0, 0.5),
      row("le guin", 2, 1, 10, null),
    ];
    const superlatives = computeSuperlatives(rows, 1);
    expect(superlatives.map((s) => s.kind)).toEqual([
      "most_collected",
      "highest_rated",
      "steadiest",
    ]);
    expect(superlatives[1].row.key).toBe("le guin");
    expect(superlatives[2].row.key).toBe("cortazar");
  });

  it("answers nothing for an empty ranking", () => {
    expect(computeSuperlatives([], 2)).toEqual([]);
  });
});

describe("chronologyBuckets", () => {
  function decadeRow(decade: string, count: number, mean: number | null) {
    return row(decade, count, count, mean);
  }

  it("fills a gap between decades that hold entries as a zero-count bucket", () => {
    const rows = [decadeRow("2000", 6, 8.1), decadeRow("1960", 3, 7.0)];
    expect(chronologyBuckets(rows)).toEqual([
      { decade: 1960, label: "1960", count: 3, meanScore: 7.0 },
      { decade: 1970, label: "1970s", count: 0, meanScore: null },
      { decade: 1980, label: "1980s", count: 0, meanScore: null },
      { decade: 1990, label: "1990s", count: 0, meanScore: null },
      { decade: 2000, label: "2000", count: 6, meanScore: 8.1 },
    ]);
  });

  it("returns nothing for an empty ranking", () => {
    expect(chronologyBuckets([])).toEqual([]);
  });

  it("returns exactly one bucket when every entry shares a decade", () => {
    expect(chronologyBuckets([decadeRow("2010", 4, 6.5)])).toEqual([
      { decade: 2010, label: "2010", count: 4, meanScore: 6.5 },
    ]);
  });
});

function insight(rows: InsightRow[]): Insight {
  return {
    type: "book",
    key: "decade",
    metric: "count",
    min_rated: 2,
    rows,
    next_cursor: null,
    suppressed: [],
    no_rated_groups: false,
    null_count: 0,
    total_entries: rows.reduce((sum, row) => sum + row.count, 0),
    rated_entries: 0,
  };
}

describe("resolveAnsweredKeys", () => {
  it("resolves a rollup key and its fine grain to one answered entry", () => {
    const decade = insight([row("2000", 6, 0, null)]);
    const year = insight([row("2001", 6, 0, null)]);
    const options = [
      {
        name: "decade",
        label: "Decade",
        grain: { name: "year", label: "Year" },
      },
    ];
    const byKey = new Map([
      ["decade", decade],
      ["year", year],
    ]);

    const answered = resolveAnsweredKeys(options, byKey);

    expect(answered).toHaveLength(1);
    expect(answered[0].insight).toBe(decade);
    expect(answered[0].grainInsight).toBe(year);
  });

  it("drops a key whose ranking has not arrived yet", () => {
    const options = [{ name: "creators", label: "Authors" }];
    expect(resolveAnsweredKeys(options, new Map())).toEqual([]);
  });

  it("leaves grainInsight undefined when the fine grain has not arrived yet", () => {
    const decade = insight([row("2000", 6, 0, null)]);
    const options = [
      {
        name: "decade",
        label: "Decade",
        grain: { name: "year", label: "Year" },
      },
    ];
    const answered = resolveAnsweredKeys(
      options,
      new Map([["decade", decade]]),
    );
    expect(answered).toHaveLength(1);
    expect(answered[0].grainInsight).toBeUndefined();
  });
});

describe("insightGridSpan", () => {
  it("gives the first card after the hero two of the next three's width", () => {
    expect(insightGridSpan(0)).toBe(8);
    expect(insightGridSpan(1)).toBe(4);
    expect(insightGridSpan(2)).toBe(4);
    expect(insightGridSpan(3)).toBe(4);
  });
});
