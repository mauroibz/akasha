import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { findToast } from "@/test/toast";
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
          <Route path="/" element={<h1>Library page</h1>} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("AddPage", () => {
  it("debounces provider search and offers keyboard-accessible manual fallback", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/shelves" ||
      String(input) === "/api/health/providers"
        ? new Response(
            String(input) === "/api/shelves"
              ? "[]"
              : JSON.stringify({ providers: [], degraded: false }),
          )
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
    // One search request for the whole typed string, not one per keystroke.
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.filter(([input]) =>
            String(input).startsWith("/api/search"),
          ),
      ).toHaveLength(1),
    );
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
          : String(input) === "/api/health/providers"
            ? new Response(JSON.stringify({ providers: [], degraded: false }))
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
    expect(await findToast("Already in your library")).toBeInTheDocument();
  });

  it("confirms a successful add on the visible toast surface", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/shelves"
        ? new Response("[]")
        : String(input) === "/api/health/providers"
          ? new Response(JSON.stringify({ providers: [], degraded: false }))
          : new Response(
              JSON.stringify({
                entry: { id: 11 },
                already_exists: false,
                near_matches: [],
              }),
              { status: 201 },
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
    await screen.findByRole("heading", { name: /library page/i });
    expect(await findToast("Book added")).toBeInTheDocument();
  });

  it("refuses an empty title and keeps everything else typed", async () => {
    const request = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input) === "/api/shelves"
          ? new Response("[]")
          : new Response(JSON.stringify({ providers: [], degraded: false })),
      );
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(
      screen.getByLabelText(/^authors, comma separated$/i),
      "Julio Cortázar",
    );
    await userEvent.type(screen.getByLabelText(/^year$/i), "1963");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );

    // The field error is announced and tied to the control that caused it.
    const title = screen.getByLabelText(/^title$/i);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /a book needs a title/i,
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
    expect(screen.getByLabelText(/^authors, comma separated$/i)).toHaveValue(
      "Julio Cortázar",
    );
    expect(screen.getByLabelText(/^year$/i)).toHaveValue(1963);
  });

  it("refuses a malformed ISBN without discarding the rest of the form", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      String(input) === "/api/shelves"
        ? new Response("[]")
        : new Response(JSON.stringify({ providers: [], degraded: false })),
    );
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(screen.getByLabelText(/^title$/i), "Rayuela");
    await userEvent.type(screen.getByLabelText(/^isbn$/i), "not-an-isbn");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/isbn/i);
    expect(screen.getByLabelText(/^title$/i)).toHaveValue("Rayuela");
    expect(screen.getByLabelText(/^isbn$/i)).toHaveValue("not-an-isbn");
  });

  it("requires explicit confirmation before adding a near-match edition", async () => {
    let posts = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves") return new Response("[]");
      if (String(input) === "/api/health/providers")
        return new Response(JSON.stringify({ providers: [], degraded: false }));
      posts += 1;
      if (posts === 1)
        return new Response(
          JSON.stringify({
            error: {
              code: "near_match_confirmation_required",
              details: { entry_ids: [4] },
            },
          }),
          { status: 409 },
        );
      return new Response(
        JSON.stringify({
          entry: { id: 8 },
          already_exists: false,
          near_matches: [4],
        }),
        { status: 201 },
      );
    });
    renderPage();
    await userEvent.click(
      screen.getByRole("button", { name: /enter manually/i }),
    );
    await userEvent.type(screen.getByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /similar edition/i,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /add separate edition/i }),
    );
    await screen.findByRole("heading", { name: /library page/i });
    expect(posts).toBe(2);
  });
});
