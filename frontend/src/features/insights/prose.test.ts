import { describe, expect, it } from "vitest";

import type { InsightRow, InsightSummary } from "@/api/library";
import {
  chronologySentence,
  leadSentence,
  modalScore,
  rankedSentence,
  ratingSentence,
  readsAsShares,
  shareSentence,
  termSize,
  termsSentence,
  type Segment,
} from "@/features/insights/prose";

const text = (segments: Segment[] | null) =>
  (segments ?? []).map((segment) => segment.text).join("");
const figures = (segments: Segment[] | null) =>
  (segments ?? [])
    .filter((segment) => segment.em)
    .map((segment) => segment.text);
const books = (count: number) => `${count} ${count === 1 ? "book" : "books"}`;

const row = (
  label: string,
  count: number,
  mean: number | null = null,
): InsightRow => ({
  key: label.toLowerCase(),
  label,
  count,
  rated_count: mean === null ? 0 : count,
  mean_score: mean,
  score_spread: null,
  covers: [],
});

const summary: InsightSummary = {
  type: "book",
  held: 142,
  finished: 58,
  rated: 119,
  unrated: 23,
  modal_score: 8,
  earliest: { entry_id: 1, title: "Pedro Páramo", year: 1955 },
};

describe("the lead sentence", () => {
  it("carries the figures that matter", () => {
    const segments = leadSentence({
      summary,
      noun: books,
      leader: { label: "Julio Cortázar", count: 7 },
    });
    expect(text(segments)).toBe(
      "You keep 142 books and have finished 58. You rate generously. You return most to Julio Cortázar.",
    );
    expect(figures(segments)).toEqual([
      "142 books",
      "58",
      "generously",
      "Julio Cortázar",
    ]);
    // Two scores are too few to judge from.
    expect(
      text(leadSentence({ summary: { ...summary, rated: 2 }, noun: books })),
    ).toBe("You keep 142 books and have finished 58.");
  });

  it("says less when there is less to say", () => {
    const segments = leadSentence({
      summary: { ...summary, held: 1, finished: 0, modal_score: null },
      noun: books,
      leader: { label: "Someone", count: 1 },
    });
    expect(text(segments)).toBe("You keep 1 book.");
  });
});

describe("the rating sentence", () => {
  it("names the usual score, the tens and the floor", () => {
    expect(text(ratingSentence([0, 0, 0, 0, 3, 6, 14, 21, 9, 1]))).toBe(
      "Most of what you rate lands at 8. You have given one 10, and nothing below a 5.",
    );
  });

  it("is silent with nothing rated", () => {
    expect(ratingSentence([0, 0, 0, 0, 0, 0, 0, 0, 0, 0])).toBeNull();
  });

  it("breaks a tie towards the higher score", () => {
    expect(modalScore([0, 0, 0, 0, 0, 0, 2, 2, 0, 0])).toBe(8);
  });
});

describe("the other sections", () => {
  it("names the leader, by count or by average", () => {
    const leader = row("Ursula K. Le Guin", 5, 9.2);
    expect(text(rankedSentence(leader, "count", books))).toBe(
      "You return most to Ursula K. Le Guin: 5 books.",
    );
    expect(text(rankedSentence(leader, "score", books))).toBe(
      "Ursula K. Le Guin has your best average: 9.2 over 5 books.",
    );
  });

  it("lists the top three terms", () => {
    expect(
      text(
        termsSentence([
          row("Fiction", 41),
          row("Poetry", 9),
          row("Essays", 4),
          row("War", 2),
        ]),
      ),
    ).toBe("Mostly Fiction, Poetry and Essays.");
  });

  it("finds the half-way decade and the oldest item", () => {
    const buckets = [
      { decade: 1950, label: "1950s", count: 2, meanScore: null },
      { decade: 1960, label: "1960s", count: 3, meanScore: null },
      { decade: 2010, label: "2010s", count: 6, meanScore: null },
    ];
    expect(text(chronologySentence(buckets, summary.earliest))).toBe(
      "Half of them are from the 2010s. The oldest is Pedro Páramo, from 1955.",
    );
  });

  it("states a share and what follows it", () => {
    expect(
      text(
        shareSentence([
          row("Spanish", 74),
          row("English", 62),
          row("French", 6),
        ]),
      ),
    ).toBe("Spanish for 52%, then English.");
    expect(text(shareSentence([row("Spanish", 3)]))).toBe("All Spanish.");
  });

  it("sizes terms in steps and picks the bar for few values", () => {
    expect(termSize(41, 41)).toBe("text-4xl");
    expect(termSize(3, 41)).toBe("text-lg");
    expect(readsAsShares([row("a", 1), row("b", 1)])).toBe(true);
    expect(readsAsShares([row("a", 1)])).toBe(false);
  });
});
