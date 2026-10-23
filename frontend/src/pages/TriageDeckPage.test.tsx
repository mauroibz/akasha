import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TriageDeckPage } from "./TriageDeckPage";

const bookType = {
  id: "book",
  label: "Book",
  fields: [],
  statuses: [
    { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
    { value: "read", label: "Read", choosable: true, hotkey: "r" },
    { value: "to_read", label: "To read", choosable: true, hotkey: "t" },
    { value: "dropped", label: "Dropped", choosable: true, hotkey: "d" },
  ],
  default_status: "read",
  entry_fields: [],
  formats: [],
  entry_panel_label: "Your reading data",
};

function entry(id: number, title: string, extra: object = {}) {
  return {
    id,
    item_id: id,
    status: "unsorted",
    score: null,
    notes: null,
    date_added: "2026-01-01T00:00:00Z",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: null,
    score_provisional: false,
    suggested_status: null,
    shelves: [],
    formats: [],
    item: {
      id,
      type: "book",
      title,
      subtitle: null,
      year: 1958,
      creator: "George Saunders",
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    ...extra,
  };
}

const longTitle =
  "A Swim in a Pond in the Rain: In Which Four Russians Give a Master Class";

function stubApi(
  entries = [entry(1, longTitle), entry(2, "Lincoln in the Bardo")],
  shelves: object[] = [],
) {
  const calls: Array<{ method: string; url: string; body?: unknown }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    calls.push({
      method,
      url,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });
    if (url === "/api/item-types")
      return new Response(JSON.stringify([bookType]));
    if (url === "/api/shelves") return new Response(JSON.stringify(shelves));
    if (url.startsWith("/api/entries?"))
      return new Response(
        JSON.stringify({
          items: entries,
          next_cursor: null,
          total: entries.length,
          facets: {
            status_counts: { unsorted: entries.length },
            status_counts_by_type: {},
            format_counts: {},
          },
        }),
      );
    if (method === "PATCH" && url.startsWith("/api/entries/")) {
      const id = Number(url.split("/").at(-1));
      return new Response(
        JSON.stringify({
          ...entries.find((row) => row.id === id),
          ...JSON.parse(String(init?.body)),
        }),
      );
    }
    return new Response("[]");
  });
  return calls;
}

const patches = (calls: ReturnType<typeof stubApi>) =>
  calls.filter((call) => call.method === "PATCH");

function renderDeck() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/inbox/deck"]}>
        <Routes>
          <Route path="/inbox/deck" element={<TriageDeckPage />} />
          <Route path="/inbox" element={<div>The inbox list</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("TriageDeckPage", () => {
  it("shows one card with its whole title and files it in one request", async () => {
    const calls = stubApi();
    renderDeck();

    expect(
      await screen.findByRole("heading", { name: longTitle }),
    ).toBeVisible();
    expect(screen.getByTestId("deck-left")).toHaveTextContent("2 left");

    await userEvent.click(screen.getByRole("button", { name: "To read" }));
    await userEvent.click(screen.getByRole("button", { name: "Score 8" }));
    await userEvent.click(
      screen.getByRole("button", { name: "File as To read" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Lincoln in the Bardo" }),
    ).toBeVisible();
    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    expect(patches(calls)[0]).toMatchObject({
      url: "/api/entries/1",
      body: { status: "to_read", score: 8 },
    });
  });

  it("files an untouched provisional score as it was, leaving it provisional", async () => {
    const calls = stubApi([
      entry(1, "Tenth of December", {
        score: 7,
        score_provisional: true,
        suggested_status: "read",
      }),
    ]);
    renderDeck();
    await screen.findByText(/score from the import/i);
    await userEvent.click(screen.getByRole("button", { name: "File as Read" }));
    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    expect(patches(calls)[0].body).toEqual({ status: "read" });
  });

  it("passes a card without writing, and brings it back after the rest", async () => {
    const calls = stubApi();
    renderDeck();
    await screen.findByRole("heading", { name: longTitle });

    await userEvent.click(screen.getByRole("button", { name: /later/i }));
    expect(
      await screen.findByRole("heading", { name: "Lincoln in the Bardo" }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "File as Read" }));

    // The round ends on the passed card's offer, not on the card itself.
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Go through the 1 you passed",
      }),
    );
    expect(
      await screen.findByRole("heading", { name: longTitle }),
    ).toBeVisible();
    expect(patches(calls).map((call) => call.url)).toEqual(["/api/entries/2"]);
  });

  it("ends a round of passes in one sentence with one full stop", async () => {
    stubApi([entry(1, "Tenth of December")]);
    renderDeck();
    await screen.findByRole("heading", { name: "Tenth of December" });
    await userEvent.click(screen.getByRole("button", { name: /later/i }));
    expect(
      await screen.findByText("Nothing filed this time · 1 left for later."),
    ).toBeVisible();
  });

  it("undoes a filed card: it comes back and is put back as it was", async () => {
    const calls = stubApi();
    renderDeck();
    await screen.findByRole("heading", { name: longTitle });
    await userEvent.click(screen.getByRole("button", { name: "File as Read" }));
    await screen.findByRole("heading", { name: "Lincoln in the Bardo" });

    await userEvent.click(screen.getByRole("button", { name: /undo/i }));
    expect(
      await screen.findByRole("heading", { name: longTitle }),
    ).toBeVisible();
    await waitFor(() => expect(patches(calls)).toHaveLength(2));
    expect(patches(calls)[1]).toMatchObject({
      url: "/api/entries/1",
      body: { status: "unsorted" },
    });
  });

  it("is driven from the keyboard: status keys, digits, arrows", async () => {
    const calls = stubApi();
    renderDeck();
    await screen.findByRole("heading", { name: longTitle });

    await userEvent.keyboard("d0{ArrowRight}");
    await screen.findByRole("heading", { name: "Lincoln in the Bardo" });
    await userEvent.keyboard("{ArrowLeft}");
    await screen.findByRole("button", { name: "Go through the 1 you passed" });

    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    expect(patches(calls)[0].body).toEqual({ status: "dropped", score: 10 });
  });

  it("toggles shelves and writes them with the card", async () => {
    const calls = stubApi(
      [entry(1, "Pastoralia")],
      [{ id: 4, name: "Stories", slug: "stories", entry_count: 0 }],
    );
    renderDeck();
    await userEvent.click(
      await screen.findByRole("button", { name: /stories/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: "File as Read" }));
    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    expect(patches(calls)[0].body).toEqual({ status: "read", shelf_ids: [4] });
    expect(await screen.findByText("Inbox clear")).toBeVisible();
  });

  it("turns the card over to its back", async () => {
    stubApi([entry(1, "Pastoralia", { suggested_status: "to_read" })]);
    renderDeck();
    await userEvent.click(
      await screen.findByRole("button", { name: /turn over for details/i }),
    );
    expect(
      screen.getByRole("button", { name: /turn to the cover/i }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Import says").nextSibling).toHaveTextContent(
      "To read",
    );
  });
});
