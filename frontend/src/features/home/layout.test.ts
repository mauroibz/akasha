import { describe, expect, it } from "vitest";

import { packRows } from "./layout";

const spans = (modules: Parameters<typeof packRows>[0]) =>
  packRows(modules).map(({ key, span }) => `${key}:${span}`);

describe("packRows", () => {
  it("puts two showcases side by side, 7 and 5, and gives a band the whole row (Sprint 150)", () => {
    expect(
      spans([
        { key: "now", size: "L" },
        { key: "year:book", size: "L" },
        { key: "suggested", size: "M" },
        { key: "lately", size: "L" },
        { key: "question", size: "S" },
      ]),
    ).toEqual([
      "now:12",
      "year:book:7",
      "suggested:5",
      "lately:12",
      "question:12",
    ]);
  });

  it("gives a module the whole row when nothing fits beside it", () => {
    expect(
      spans([
        { key: "next", size: "L" },
        { key: "year:book", size: "L" },
      ]),
    ).toEqual(["next:12", "year:book:12"]);
  });

  it("shares a row's spare columns so it ends without a gap", () => {
    expect(
      spans([
        { key: "shelf:1", size: "S" },
        { key: "question", size: "S" },
        { key: "shelf:2", size: "S" },
      ]),
    ).toEqual(["shelf:1:4", "question:4", "shelf:2:4"]);
    expect(
      spans([
        { key: "suggested", size: "M" },
        { key: "question", size: "S" },
      ]),
    ).toEqual(["suggested:7", "question:5"]);
  });

  it("starts a new row for a module that does not fit", () => {
    expect(
      spans([
        { key: "year:book", size: "L" },
        { key: "next", size: "L" },
      ]),
    ).toEqual(["year:book:12", "next:12"]);
  });
});
