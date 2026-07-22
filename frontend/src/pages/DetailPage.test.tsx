import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { DetailPage } from "./DetailPage";

const entry = {
  id: 7,
  item_id: 3,
  status: "reading",
  score: 8,
  notes: "Cached note",
  date_added: "2026-07-22",
  date_started: null,
  date_finished: null,
  reread_count: 0,
  score_provisional: false,
  suggested_status: null,
  item: {
    id: 3,
    type: "book",
    title: "Rayuela",
    subtitle: null,
    year: 1963,
    sort_author: "Julio Cortázar",
    cover_path: null,
    metadata: { authors: ["Julio Cortázar"], publisher: "Sudamericana" },
    identifiers: {},
    sources: [{ source: "openlibrary", source_id: "OL1M", is_primary: true }],
  },
  shelves: [],
};

function renderPage() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/books/7"]}>
        <Routes>
          <Route path="/books/:entryId" element={<DetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

it("renders cached detail and persists opinion and metadata edits", async () => {
  const request = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/shelves") return new Response("[]");
      if (!init) return new Response(JSON.stringify(entry));
      if (url.includes("/entries/"))
        return new Response(JSON.stringify({ ...entry, notes: "Loved it" }));
      return new Response(
        JSON.stringify({ ...entry.item, title: "Rayuela corregida" }),
      );
    });
  renderPage();
  expect(await screen.findByRole("heading", { name: "Rayuela" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /edit opinion/i }));
  await userEvent.clear(screen.getByLabelText(/notes/i));
  await userEvent.type(screen.getByLabelText(/notes/i), "Loved it");
  await userEvent.click(screen.getByRole("button", { name: /save opinion/i }));
  await userEvent.click(
    screen.getByRole("button", { name: /edit book metadata/i }),
  );
  await userEvent.clear(screen.getByLabelText(/^title$/i));
  await userEvent.type(screen.getByLabelText(/^title$/i), "Rayuela corregida");
  await userEvent.click(screen.getByRole("button", { name: /save metadata/i }));
  expect(request).toHaveBeenCalledWith(
    "/api/entries/7",
    expect.objectContaining({ method: "PATCH" }),
  );
  expect(request).toHaveBeenCalledWith(
    "/api/items/3",
    expect.objectContaining({ method: "PATCH" }),
  );
});
