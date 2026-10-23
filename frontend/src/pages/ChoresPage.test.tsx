import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChoresPage } from "./ChoresPage";

const bookType = {
  id: "book",
  label: "Book",
  fields: [],
  statuses: [
    { value: "to_read", label: "To read", choosable: true, planned: true },
  ],
};

const page = (total: number) =>
  new Response(
    JSON.stringify({
      items: [],
      next_cursor: null,
      total,
      facets: {
        status_counts: { unsorted: 4 },
        status_counts_by_type: {},
        format_counts: {},
      },
    }),
  );

afterEach(() => vi.restoreAllMocks());

describe("ChoresPage (Sprint 112)", () => {
  it("lists each chore with how many cards it holds", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify([bookType]));
      if (url.includes("cover=missing")) return page(12);
      if (url === "/api/duplicates")
        return new Response(JSON.stringify([{}, {}]));
      if (url.includes("status=to_read")) return page(30);
      if (url.includes("status=unsorted")) return page(4);
      return new Response("[]");
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <ChoresPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const list = await screen.findByRole("list", { name: "Chores" });
    const inbox = within(list).getByRole("link", { name: /Sort the inbox/ });
    expect(inbox).toHaveAttribute("href", "/inbox/deck");
    expect(await within(inbox).findByText("4")).toBeVisible();
    const planned = within(list).getByRole("link", { name: /Still want this/ });
    expect(planned).toHaveAttribute("href", "/deck/planned");
    expect(await within(planned).findByText("30")).toBeVisible();
    const covers = within(list).getByRole("link", { name: /Find a cover/ });
    expect(covers).toHaveAttribute("href", "/deck/covers");
    expect(await within(covers).findByText("12")).toBeVisible();
    const duplicates = within(list).getByRole("link", { name: /Duplicates/ });
    expect(duplicates).toHaveAttribute("href", "/deck/duplicates");
    expect(await within(duplicates).findByText("2")).toBeVisible();
  });
});
