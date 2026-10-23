import { describe, expect, it } from "vitest";

import { boardFrom, moveTo, proposals, rowsToRank } from "./board";

const entries = [
  { id: 1, score: 9, score_rank: null },
  { id: 2, score: 8, score_rank: 2 },
  { id: 3, score: 8, score_rank: 1 },
  { id: 4, score: 8, score_rank: null },
  { id: 5, score: 6, score_rank: null },
];

describe("the tier board (Sprint 117)", () => {
  it("lays scores out in rows, ranked first in their order", () => {
    const board = boardFrom(entries);
    expect(board[9]).toEqual([1]);
    expect(board[8]).toEqual([3, 2, 4]);
    expect(board[7]).toEqual([]);
    expect(board[6]).toEqual([5]);
  });

  it("a move inside a row only reorders it, and that row's order is saved at once", () => {
    const board = boardFrom(entries);
    const moved = moveTo(board, 4, 8, 0);
    expect(moved[8]).toEqual([4, 3, 2]);
    expect(proposals(moved, entries)).toEqual([]);
    expect(rowsToRank(moved, board, entries)).toEqual([[4, 3, 2]]);
  });

  it("a move to another row is a proposal, not a write", () => {
    const board = boardFrom(entries);
    const moved = moveTo(board, 2, 9, 1);
    expect(moved[9]).toEqual([1, 2]);
    expect(moved[8]).toEqual([3, 4]);
    expect(proposals(moved, entries)).toEqual([{ id: 2, from: 8, to: 9 }]);
    // A row holding a proposal waits for Apply; the row it left can be saved.
    expect(rowsToRank(moved, board, entries)).toEqual([[3, 4]]);
  });

  it("moving it back withdraws the proposal", () => {
    const board = boardFrom(entries);
    const there = moveTo(board, 2, 9, 0);
    const back = moveTo(there, 2, 8, 1);
    expect(proposals(back, entries)).toEqual([]);
    expect(back[8]).toEqual([3, 2, 4]);
  });
});
