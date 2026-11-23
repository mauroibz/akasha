import { describe, expect, it } from "vitest";

import { packRows } from "./layout";

const spans = (modules: Parameters<typeof packRows>[0]) =>
  packRows(modules).map(({ key, span }) => `${key}:${span}`);

describe("packRows", () => {
  it("puts the year and Lately side by side, 7 and 5", () => {
    expect(
      spans([
        { key: "now", size: "M" },
        { key: "next", size: "L" },
        { key: "year", size: "L" },
        { key: "lately", size: "M" },
        { key: "libraries", size: "L" },
      ]),
    ).toEqual(["now:5", "next:7", "year:7", "lately:5", "libraries:12"]);
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
        { key: "tidy", size: "S" },
        { key: "question", size: "S" },
        { key: "shelves", size: "S" },
      ]),
    ).toEqual(["tidy:4", "question:4", "shelves:4"]);
    expect(
      spans([
        { key: "now", size: "M" },
        { key: "tidy", size: "S" },
      ]),
    ).toEqual(["now:7", "tidy:5"]);
  });

  it("starts a new row for a module that does not fit", () => {
    expect(
      spans([
        { key: "now", size: "L" },
        { key: "next", size: "L" },
      ]),
    ).toEqual(["now:12", "next:12"]);
  });
});
