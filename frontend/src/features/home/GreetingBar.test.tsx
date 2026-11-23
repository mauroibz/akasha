import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GreetingBar } from "./GreetingBar";
import { emptyHome, fullHome, renderWithRouter, types } from "./testHome";

describe("GreetingBar", () => {
  it("names the day, the day of what is under way, and the library's totals", () => {
    renderWithRouter(
      <GreetingBar greeting={fullHome().greeting} types={types} />,
    );
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(
      "Sunday. Day 32 of Designing Data-Intensive Applications.",
    );
    expect(screen.getByText("345")).toBeVisible();
    expect(screen.getByText(/of 24 books in 2026/)).toBeVisible();
    expect(screen.getByText("41")).toBeVisible();
    // The pile's count opens the pile as a list (DEC-192).
    expect(
      screen.getByRole("link", { name: "41 on the pile" }),
    ).toHaveAttribute("href", "/pile");
  });

  it("leaves the day count out when nothing under way has a start date", () => {
    const greeting = fullHome().greeting;
    greeting.active = { entry: greeting.active!.entry, day: null };
    renderWithRouter(<GreetingBar greeting={greeting} types={types} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Sunday. Designing Data-Intensive Applications.",
    );
    expect(screen.queryByText(/Day \d+/)).toBeNull();
  });

  it("says only the date when nothing is under way", () => {
    renderWithRouter(
      <GreetingBar greeting={emptyHome().greeting} types={types} />,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Sunday, 22 November.",
    );
  });
});
