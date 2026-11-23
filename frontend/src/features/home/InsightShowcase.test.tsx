import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InsightShowcase } from "./InsightShowcase";
import { parseInsightKey } from "./layout";
import { renderWithRouter, types } from "./testHome";

afterEach(() => vi.restoreAllMocks());

function serve(body: object) {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      urls.push(String(input));
      return new Response(JSON.stringify(body));
    }),
  );
  return urls;
}

describe("InsightShowcase (Sprint 142, DEC-193)", () => {
  it("takes a key apart", () => {
    expect(parseInsightKey("insight:book:scores")).toEqual({
      type: "book",
      section: "scores",
    });
    expect(parseInsightKey("shelf:7")).toBeNull();
  });

  it("says how a medium is rated, in the Journal's sentence", async () => {
    const urls = serve({
      type: "book",
      counts: [0, 0, 0, 1, 0, 2, 3, 9, 4, 2],
      rated_count: 21,
      unrated_count: 3,
    });
    renderWithRouter(
      <InsightShowcase
        moduleKey="insight:book:scores"
        label="How you rate books"
        types={types}
      />,
    );
    const box = await screen.findByRole("region", {
      name: "How you rate books",
    });
    expect(
      await within(box).findByText(/Most of what you rate lands at/),
    ).toBeVisible();
    expect(
      urls.some((url) => url.startsWith("/api/insights/scores?type=book")),
    ).toBe(true);
  });

  it("says so when nothing is scored", async () => {
    serve({
      type: "book",
      counts: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
      rated_count: 0,
      unrated_count: 4,
    });
    renderWithRouter(
      <InsightShowcase
        moduleKey="insight:book:scores"
        label="How you rate books"
        types={types}
      />,
    );
    expect(await screen.findByText(/Nothing scored yet/)).toBeVisible();
  });

  it("names what a medium returns to most, each row a way into the library", async () => {
    const urls = serve({
      rows: [
        {
          key: "horror",
          label: "Horror",
          count: 12,
          rated_count: 10,
          mean_score: 8.1,
          score_spread: 1,
          covers: [],
        },
        {
          key: "fantasy",
          label: "Fantasy",
          count: 7,
          rated_count: 0,
          mean_score: null,
          score_spread: null,
          covers: [],
        },
      ],
      next_cursor: null,
      suppressed: [],
    });
    renderWithRouter(
      <InsightShowcase
        moduleKey="insight:book:subjects"
        label="Books by subjects"
        types={types}
      />,
    );
    expect(await screen.findByText(/You return most to/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Horror" })).toHaveAttribute(
      "href",
      "/?type=book&key=subjects&value=horror&label=Horror",
    );
    expect(
      urls.some(
        (url) =>
          url.includes("/api/insights?") &&
          url.includes("key=subjects") &&
          url.includes("limit=3"),
      ),
    ).toBe(true);
  });
});
