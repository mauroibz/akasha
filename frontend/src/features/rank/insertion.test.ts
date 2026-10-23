import { describe, expect, it } from "vitest";

import { answer, start, type Ranking } from "./insertion";

/** Answer every question by a hidden true order, counting the questions asked. */
function settle(initial: Ranking, truth: number[]) {
  let state = initial;
  let asked = 0;
  while (state.question) {
    asked += 1;
    const { candidate, against } = state.question;
    state = answer(
      state,
      truth.indexOf(candidate) < truth.indexOf(against)
        ? "candidate"
        : "against",
    );
  }
  return { state, asked };
}

describe("ranking by choosing between two (Sprint 116)", () => {
  it("places each new entry by halving, and ends in the true order", () => {
    const truth = [5, 3, 8, 1, 7, 2, 6, 4];
    const { state, asked } = settle(start([], truth.slice().sort()), truth);
    expect(state.ranked).toEqual(truth);
    // Binary insertion: at most ceil(log2(k + 1)) questions for the k-th entry.
    expect(asked).toBeLessThanOrEqual(0 + 1 + 2 + 2 + 3 + 3 + 3 + 3);
  });

  it("keeps an existing order and only places the newcomers", () => {
    const { state } = settle(start([1, 2, 3], [4]), [1, 4, 2, 3]);
    expect(state.ranked).toEqual([1, 4, 2, 3]);
  });

  it("puts one of about the same right after the other", () => {
    let state = start([1, 2, 3], [9]);
    // Asked against the middle one first.
    expect(state.question).toEqual({ candidate: 9, against: 2 });
    state = answer(state, "same");
    expect(state.question).toBeNull();
    expect(state.ranked).toEqual([1, 2, 9, 3]);
  });

  it("can set one aside for later without placing it", () => {
    let state = start([1], [2, 3]);
    state = answer(state, "skip");
    expect(state.skipped).toEqual([2]);
    expect(state.question).toEqual({ candidate: 3, against: 1 });
  });

  it("asks nothing of the first one: alone, it is first", () => {
    const state = start([], [7]);
    expect(state.question).toBeNull();
    expect(state.ranked).toEqual([7]);
  });
});
