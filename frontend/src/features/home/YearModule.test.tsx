import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { YearModule } from "./YearModule";
import { fitMonths, MONTH_CELLS, yearCells } from "./year";
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

  it("fills the height it is given with larger covers rather than leaving it empty", () => {
    // Beside Lately on a wide screen: a 45 px month column and 250 px of strip.
    const roomy = fitMonths({ width: 45, height: 250 }, 3);
    expect(roomy.columns).toBe(1);
    expect(roomy.cells).toBeGreaterThanOrEqual(3);
    // Every month's covers stand in one column, as tall as the column is wide allows.
    expect(roomy.coverHeight).toBeCloseTo(45 * 1.5);
    // A short strip takes two columns before it hides a cover behind a count.
    const short = fitMonths({ width: 45, height: 110 }, 3);
    expect(short.columns).toBe(2);
    expect(short.cells).toBeGreaterThanOrEqual(3);
  });

  it("shows more than four a month when there is room, and counts the rest", () => {
    expect(
      fitMonths({ width: 45, height: 600 }, 9).cells,
    ).toBeGreaterThanOrEqual(8);
    const crowded = fitMonths({ width: 45, height: 120 }, 24);
    expect(crowded.columns).toBe(3);
    expect(crowded.cells).toBeLessThan(24);
  });

  it("keeps the old two columns of four until it has been measured", () => {
    expect(fitMonths({ width: 0, height: 0 }, 6)).toMatchObject({
      columns: 2,
      cells: MONTH_CELLS,
      coverHeight: null,
    });
  });
});
