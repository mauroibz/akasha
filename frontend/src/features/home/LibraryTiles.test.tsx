import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LibraryTiles } from "./LibraryTiles";
import { fullHome, renderWithRouter, types } from "./testHome";

describe("LibraryTiles", () => {
  it("draws one tile per domain the payload names, each opening its library", () => {
    renderWithRouter(<LibraryTiles tiles={fullHome().domains} types={types} />);
    const books = screen.getByRole("link", { name: /105 Books/ });
    expect(books).toHaveAttribute("href", "/library?type=book");
    expect(screen.getByRole("link", { name: /148 Albums/ })).toHaveAttribute(
      "href",
      "/library?type=album",
    );
    expect(within(books).getByText("57 read")).toBeVisible();
    expect(within(books).getByText("41 to read")).toBeVisible();
    expect(within(books).getByText("avg 6.1")).toBeVisible();
    expect(within(books).getByText("11 without a cover")).toBeVisible();
  });

  it("names a domain the client does not know by its id rather than failing", () => {
    const tile = { ...fullHome().domains[0], item_type: "game" };
    renderWithRouter(<LibraryTiles tiles={[tile]} types={types} />);
    expect(screen.getByRole("link", { name: /105 items/i })).toHaveAttribute(
      "href",
      "/library?type=game",
    );
  });
});
