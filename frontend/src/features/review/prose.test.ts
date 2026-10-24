import { describe, expect, it } from "vitest";

import type { Segment } from "@/features/insights/prose";

import {
  bestSentence,
  changesSentence,
  leadSentence,
  monthsSentence,
} from "./prose";

const text = (segments: Segment[] | null) =>
  segments?.map((s) => s.text).join("") ?? null;
const noun = (type: string, count: number) =>
  `${count} ${type}${count === 1 ? "" : "s"}`;

describe("the year read back (Sprint 120)", () => {
  it("leads with what was finished, how it was rated, and who was returned to", () => {
    expect(
      text(
        leadSentence({
          counts: { book: 23, movie: 9, series: 6, album: 3 },
          finished: 41,
          scores: [0, 0, 0, 0, 1, 2, 5, 14, 9, 2],
          leader: { name: "Ursula K. Le Guin", count: 4 },
          noun,
        }),
      ),
    ).toBe(
      "You finished 41 things: 23 books, 9 movies, 6 seriess and 3 albums. You rated generously. You returned most to Ursula K. Le Guin.",
    );
    expect(
      text(
        leadSentence({
          counts: { book: 2 },
          finished: 2,
          scores: Array(10).fill(0),
          leader: null,
          noun,
        }),
      ),
    ).toBe("You finished 2 books.");
  });

  it("names the best of it", () => {
    expect(
      text(
        bestSentence([
          { title: "Monster", score: 10, month: "October" },
          { title: "Piranesi", score: 9, month: "March" },
          { title: "Frieren", score: 9, month: "May" },
        ]),
      ),
    ).toBe(
      "Your highest score was a 10, for Monster, in October. Two more got a 9.",
    );
    expect(
      text(bestSentence([{ title: "Solaris", score: 8, month: "May" }])),
    ).toBe("Your highest score was an 8, for Solaris, in May.");
  });

  it("says which month was busiest and which had none", () => {
    expect(
      text(
        monthsSentence(
          [3, 2, 7, 4, 3, 5, 4, 0, 3, 4, 2, 4],
          (i) =>
            [
              "January",
              "February",
              "March",
              "April",
              "May",
              "June",
              "July",
              "August",
              "September",
              "October",
              "November",
              "December",
            ][i],
        ),
      ),
    ).toBe("March was your busiest month, with seven. August had none.");
    expect(
      text(
        monthsSentence([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], () => "January"),
      ),
    ).toBe("January was your busiest month, with one. 11 months had none.");
  });

  it("says which scores changed, and why", () => {
    expect(
      text(
        changesSentence([
          { title: "Solaris", previous: 8, score: 9, reason: "reread" },
          { title: "Dune", previous: 7, score: 6, reason: "time" },
        ]),
      ),
    ).toBe(
      "You changed two scores. Solaris went up after a reread; Dune went down with time.",
    );
    expect(text(changesSentence([]))).toBeNull();
  });
});
