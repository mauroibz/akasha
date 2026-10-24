import { describe, expect, it } from "vitest";

import type { LibraryEntry } from "@/api/library";

import { mixRound, orderAfter, pairFrom } from "./five";

const e = (id: number, rank: number | null = null) =>
  ({ id, score: 8, score_rank: rank }) as unknown as LibraryEntry;

describe("five minutes (Sprint 126)", () => {
  it("asks about the first entry not yet placed, against the one above it", () => {
    expect(pairFrom([e(1, 1), e(2, 2), e(3), e(4)])?.map((x) => x.id)).toEqual([
      2, 3,
    ]);
    expect(pairFrom([e(1, 1), e(2, 2)])?.map((x) => x.id)).toEqual([1, 2]);
    expect(pairFrom([e(1)])).toBeNull();
  });

  it("writes the placed order with the answer in it, and places nothing unasked", () => {
    const all = [e(1, 1), e(2, 2), e(3), e(4)];
    expect(orderAfter(all, [all[1], all[2]], all[2])).toEqual([1, 3, 2]);
    expect(orderAfter(all, [all[1], all[2]], all[1])).toEqual([1, 2, 3]);
    const none = [e(5), e(6), e(7)];
    expect(orderAfter(none, [none[0], none[1]], none[1])).toEqual([6, 5]);
  });

  it("mixes the kinds, never more than five cards", () => {
    const round = mixRound({
      pair: [e(1), e(2)],
      gaps: [e(3), e(4), e(5)],
      old: [e(6), e(7)],
      pile: [e(8), e(9)],
    });
    expect(round.map((card) => card.kind)).toEqual([
      "pair",
      "gap",
      "old",
      "pile",
      "gap",
    ]);
    expect(
      mixRound({ pair: null, gaps: [e(3)], old: [], pile: [] }).map(
        (card) => card.kind,
      ),
    ).toEqual(["gap"]);
  });
});
