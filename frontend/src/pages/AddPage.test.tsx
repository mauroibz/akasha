import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { findToast } from "@/test/toast";
import { AddPage } from "./AddPage";

/**
 * `/add` after Sprint 029: manual entry, and nothing else.
 *
 * Searching, the results list, the provider-health notice, the near-match
 * confirmation and the confirm form's own behaviour all moved. They are not gone:
 * the flow from `/` is tested against the functionality inventory in
 * `HomePage.test.tsx`, and the form itself in `features/add/AddForm.test.tsx`.
 * What is left here is what this route is now for.
 */

function renderPage(initialEntry = "/add") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/add" element={<AddPage />} />
          <Route path="/books/:id" element={<h1>Book detail</h1>} />
          <Route path="/" element={<h1>Library page</h1>} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

/** The two domains `GET /api/item-types` publishes (DEC-052 seam 3). */
const itemTypes = [
  { id: "book", label: "Book", fields: [] },
  { id: "album", label: "Album", fields: [] },
];

function stubApi(onCreate?: () => Response) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/entries" && init?.method === "POST")
        return (
          onCreate?.() ??
          new Response(
            JSON.stringify({
              entry: { id: 11 },
              already_exists: false,
              near_matches: [],
            }),
            { status: 201 },
          )
        );
      return new Response(JSON.stringify({ providers: [], degraded: false }));
    });
}

describe("AddPage", () => {
  it("is a working deep link straight to the manual form", async () => {
    stubApi();
    renderPage();

    // AC6. No search, no results list, no step before the form.
    expect(
      await screen.findByRole("heading", { name: /enter by hand/i }),
    ).toBeVisible();
    expect(screen.getByLabelText(/^title$/i)).toBeVisible();
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /enter manually/i }),
    ).toBeNull();
  });

  it("puts the cursor in the title field, which is the only thing to do here", async () => {
    stubApi();
    renderPage();

    // Inventory row 9: the manual path's first focus.
    await waitFor(() =>
      expect(screen.getByLabelText(/^title$/i)).toHaveFocus(),
    );
  });

  it("submits a manual entry once and announces exact duplicates", async () => {
    const request = stubApi(
      () =>
        new Response(
          JSON.stringify({
            entry: { id: 7 },
            already_exists: true,
            near_matches: [],
          }),
          { status: 200 },
        ),
    );
    renderPage();

    await userEvent.type(await screen.findByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    await screen.findByRole("heading", { name: /book detail/i });
    // Inventory row 10: a 200 rather than a 201, and exactly one write.
    expect(
      request.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
    expect(await findToast("Already in your library")).toBeInTheDocument();
  });

  it("confirms a successful add on the visible toast surface", async () => {
    stubApi();
    renderPage();

    await userEvent.type(await screen.findByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    await screen.findByRole("heading", { name: /library page/i });
    // The domain's own label, not the word "Book" typed into this file.
    expect(await findToast("Book added")).toBeInTheDocument();
  });

  it("refuses an empty title and keeps everything else typed", async () => {
    const request = stubApi();
    renderPage();

    await userEvent.type(
      await screen.findByLabelText(/^creators, comma separated$/i),
      "Julio Cortázar",
    );
    await userEvent.type(screen.getByLabelText(/^year$/i), "1963");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );

    // The field error is announced and tied to the control that caused it.
    const title = screen.getByLabelText(/^title$/i);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /title is required/i,
    );
    expect(title).toHaveAttribute("aria-invalid", "true");
    expect(title).toHaveAttribute(
      "aria-describedby",
      screen.getByRole("alert").id,
    );
    // Nothing was sent, and nothing typed was discarded.
    expect(
      request.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(0);
    expect(screen.getByLabelText(/^creators, comma separated$/i)).toHaveValue(
      "Julio Cortázar",
    );
    expect(screen.getByLabelText(/^year$/i)).toHaveValue(1963);
  });

  it("refuses a malformed ISBN without discarding the rest of the form", async () => {
    stubApi();
    renderPage();

    await userEvent.type(await screen.findByLabelText(/^title$/i), "Rayuela");
    await userEvent.type(screen.getByLabelText(/^isbn$/i), "not-an-isbn");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/isbn/i);
    expect(screen.getByLabelText(/^title$/i)).toHaveValue("Rayuela");
    expect(screen.getByLabelText(/^isbn$/i)).toHaveValue("not-an-isbn");
  });
});
