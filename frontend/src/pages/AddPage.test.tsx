import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddPage } from "./AddPage";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/add"]}>
        <Routes>
          <Route path="/add" element={<AddPage />} />
          <Route path="/books/:id" element={<h1>Book detail</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("AddPage", () => {
  it("debounces provider search and offers keyboard-accessible manual fallback", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/shelves"
        ? new Response("[]")
        : new Response(
            JSON.stringify([
              {
                source: "openlibrary",
                source_id: "OL1M",
                source_refs: [{ source: "openlibrary", source_id: "OL1M" }],
                title: "Rayuela",
                subtitle: null,
                authors: ["Julio Cortázar"],
                year: 1963,
                cover_url: null,
                identifiers: {},
                language: "es",
                metadata: {},
              },
            ]),
            { status: 200 },
          ),
    );
    renderPage();
    await userEvent.type(
      screen.getByRole("searchbox", { name: /search books/i }),
      "Rayuela",
    );
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByRole("button", { name: /Rayuela/i }),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    expect(screen.getByLabelText(/^title$/i)).toHaveFocus();
  });

  it("submits a manual entry once and announces exact duplicates", async () => {
    const request = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input) === "/api/shelves"
          ? new Response("[]")
          : new Response(
              JSON.stringify({
                entry: { id: 7 },
                already_exists: true,
                near_matches: [],
              }),
              { status: 200 },
            ),
      );
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(screen.getByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    await screen.findByRole("heading", { name: /book detail/i });
    expect(
      request.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
    expect(sessionStorage.getItem("akasha.toast")).toBe(
      "Already in your library",
    );
  });
});
