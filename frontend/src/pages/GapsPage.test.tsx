import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GapsPage } from "./GapsPage";

const book = {
  id: "book",
  label: "Book",
  statuses: [{ value: "read", label: "Read", finished: true }],
  entry_fields: ["date_started", "date_finished", "reread_count"],
  formats: [{ value: "physical", label: "Physical" }],
  fields: [],
};

const entry = (id: number, title: string) => ({
  id,
  status: "read",
  score: 9,
  date_started: null,
  date_finished: null,
  formats: [],
  location: "Hall",
  unknown_fields: [],
  item: { id, type: "book", title, cover_url: null, metadata: {} },
});

afterEach(() => vi.restoreAllMocks());

describe("GapsPage (Sprint 125)", () => {
  it("goes through the gaps one book at a time, then says it is done", async () => {
    const gaps = [entry(1, "Rayuela"), entry(2, "Ficciones")];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify([book]));
      if (url === "/api/gaps")
        return new Response(JSON.stringify({ entries: gaps, total: 2 }));
      const id = Number(url.split("/").pop());
      return new Response(JSON.stringify(gaps.find((row) => row.id === id)));
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <GapsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(
      await screen.findByRole("heading", { name: "Rayuela" }),
    ).toBeVisible();
    expect(screen.getByText("1 of 2")).toBeVisible();
    expect(
      await screen.findByRole("heading", { name: "When did you finish it?" }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Next book" }));
    expect(
      await screen.findByRole("heading", { name: "Ficciones" }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Next book" }));
    expect(await screen.findByText(/That's every gap/)).toBeVisible();
  });
});
