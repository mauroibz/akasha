import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { YearModule } from "./YearModule";
import { yearCells } from "./year";
import { emptyHome, fullHome, renderWithRouter, types } from "./testHome";

const today = new Date(2026, 10, 22);

describe("YearModule", () => {
  it("draws twelve months with the year's covers and marks this one", () => {
    renderWithRouter(
      <YearModule year={fullHome().year!} types={types} today={today} />,
    );
    const months = screen.getAllByRole("listitem");
    expect(months).toHaveLength(12);
    expect(months[10]).toHaveAttribute("aria-current", "date");
    expect(
      within(months[7]).getByRole("link", { name: "Slaughterhouse-Five" }),
    ).toHaveAttribute("href", "/books/20");
    expect(screen.getByText("2 / 24")).toBeVisible();
  });

  it("leaves empty slots only for what the goal still needs, from this month on", () => {
    const year = fullHome().year!;
    const cells = yearCells(year, today);
    // Months gone by are not marked short; November has its book and one slot
    // left of two a month, December two.
    expect(cells[0].empty).toBe(0);
    expect(cells[10].covers.map((c) => c.title)).toEqual(["Pálido fuego"]);
    expect(cells[10].others).toBe(1);
    expect(cells[10].empty).toBe(1);
    expect(cells[11].empty).toBe(2);
  });

  it("caps the empty slots at what the goal still needs", () => {
    const year = fullHome().year!;
    year.goals = [
      { item_type: "book", period: "year", count: 3, target: 3, done: 2 },
    ];
    const cells = yearCells(year, today);
    expect(cells.reduce((sum, cell) => sum + cell.empty, 0)).toBe(1);
  });

  it("shows every finish when no goal is set", () => {
    const year = emptyHome().year!;
    renderWithRouter(<YearModule year={year} types={types} today={today} />);
    expect(screen.getByText(/Nothing finished yet in 2026/)).toBeVisible();
  });
});
