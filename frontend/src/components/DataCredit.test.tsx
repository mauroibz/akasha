import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { DataCredit } from "./DataCredit";

test("the credit names Wikidata and TVmaze as the series data sources", () => {
  render(<DataCredit />);
  // DEC-105: TVmaze's CC BY-SA licence asks to be "properly credited as source",
  // and the owner directed that the credit be given. Both sources are named,
  // with links a reader can follow.
  expect(screen.getByText(/Series data from/)).toBeVisible();
  const wikidata = screen.getByRole("link", { name: "Wikidata" });
  const tvmaze = screen.getByRole("link", { name: "TVmaze" });
  expect(wikidata).toHaveAttribute("href", "https://www.wikidata.org");
  expect(tvmaze).toHaveAttribute("href", "https://www.tvmaze.com");
});
