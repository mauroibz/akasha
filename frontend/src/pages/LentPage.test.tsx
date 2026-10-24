import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LentPage } from "./LentPage";

const loan = (id: number, person: string, title: string, lentOn: string) => ({
  id,
  entry_id: id,
  person,
  lent_on: lentOn,
  returned_on: null,
  note: null,
  entry: {
    id,
    status: "read",
    location: "Hall",
    item: {
      id,
      type: "book",
      title,
      cover_url: null,
      metadata: {},
      identifiers: {},
    },
  },
});

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <LentPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("LentPage (Sprint 111)", () => {
  it("goes back to the shelves it stands on (Sprint 122)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]"));
    renderPage();
    expect(
      await screen.findByRole("link", { name: "← Shelves" }),
    ).toHaveAttribute("href", "/shelves");
  });

  it("lists what is out, longest out first, and takes one back", async () => {
    let out = [
      loan(1, "Sofi", "Rayuela", "2026-04-02"),
      loan(2, "Juan", "Ficciones", "2026-05-01"),
    ];
    const patches: Array<{ url: string; body: unknown }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        patches.push({ url, body: JSON.parse(String(init.body)) });
        out = out.filter((row) => !url.endsWith(`/${row.id}`));
        return new Response(JSON.stringify({}));
      }
      if (url.startsWith("/api/loans"))
        return new Response(JSON.stringify(out));
      return new Response("[]");
    });
    renderPage();
    const items = await screen.findAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Rayuela");
    expect(items[0]).toHaveTextContent("Sofi");
    expect(items[1]).toHaveTextContent("Juan");
    await userEvent
      .setup()
      .click(within(items[0]).getByRole("button", { name: "Rayuela is back" }));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0].url).toBe("/api/loans/1");
    await waitFor(() => expect(screen.queryByText("Rayuela")).toBeNull());
  });

  it("says when nothing is out", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response("[]"),
    );
    renderPage();
    expect(await screen.findByText("Nothing is lent out")).toBeVisible();
  });
});
