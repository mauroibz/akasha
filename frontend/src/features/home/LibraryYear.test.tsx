import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { HomeLibraryYear } from "@/api/home";

import { LibraryYear } from "./LibraryYear";
import { renderWithRouter, types } from "./testHome";

function year(total: number, target: number | null): HomeLibraryYear {
  return {
    item_type: "book",
    year: 2026,
    total,
    goal:
      target === null
        ? null
        : {
            item_type: "book",
            period: "year",
            count: target,
            target,
            done: total,
          },
    covers: Array.from({ length: Math.min(total, 48) }, (_, index) => ({
      entry_id: 100 + index,
      item_id: 100 + index,
      item_type: "book",
      title: `Book ${index + 1}`,
      cover_url: null,
      score: null,
    })),
  };
}

const today = new Date(2026, 10, 23);

describe("LibraryYear (DEC-192)", () => {
  it("draws a goal of 24 or fewer as slots, the next one marked", () => {
    const { container } = renderWithRouter(
      <LibraryYear year={year(2, 12)} types={types} today={today} />,
    );
    const region = screen.getByRole("region", { name: "Your 2026 books" });
    expect(within(region).getByText("of 12")).toBeVisible();
    const grid = within(region).getByRole("list", {
      name: "2 of 12 books in 2026",
    });
    expect(within(grid).getAllByRole("link")).toHaveLength(2);
    expect(container.querySelectorAll('[data-slot="next"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-slot="open"]')).toHaveLength(9);
  });

  it("without a goal, shows the year's covers and how many more", () => {
    renderWithRouter(
      <LibraryYear
        year={year(15, null)}
        types={types}
        size="M"
        today={today}
      />,
    );
    const region = screen.getByRole("region", { name: "Your 2026 books" });
    expect(within(region).getByText("finished in 2026")).toBeVisible();
    expect(
      within(region).getAllByRole("link", { name: /^Book / }),
    ).toHaveLength(12);
    expect(within(region).getByText("and 3 more")).toBeVisible();
  });

  it("above 24, the goal band's bar and the covers", () => {
    renderWithRouter(
      <LibraryYear year={year(30, 52)} types={types} size="L" today={today} />,
    );
    expect(
      screen.getByRole("img", { name: "30 of 52 books in 2026" }),
    ).toBeVisible();
    expect(screen.getAllByRole("link", { name: /^Book / })).toHaveLength(24);
    expect(screen.getByText("and 6 more")).toBeVisible();
  });
});
