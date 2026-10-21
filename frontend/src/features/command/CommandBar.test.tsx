import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { takeHandedFiles } from "@/features/import/handoff";

import { CommandBarProvider } from "./CommandBarProvider";

const entry = {
  id: 7,
  item_id: 3,
  status: "read",
  score: 9,
  score_provisional: false,
  shelves: [],
  formats: [],
  item: {
    id: 3,
    type: "book",
    title: "Rayuela",
    creator: "Julio Cortázar",
    cover_url: null,
    metadata: {},
    identifiers: {},
  },
};

const candidate = {
  source: "openlibrary",
  source_id: "OL1M",
  source_refs: [{ source: "openlibrary", source_id: "OL1M" }],
  title: "Ficciones",
  subtitle: null,
  creators: ["Jorge Luis Borges"],
  credit: null,
  year: 1944,
  cover_url: null,
  identifiers: {},
  language: "es",
  metadata: {},
};

function renderBar() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/"]}>
        <CommandBarProvider>
          <Routes>
            <Route path="/" element={<p>Library page</p>} />
            <Route path="/books/:id" element={<p>Detail page</p>} />
            <Route path="/insights" element={<p>Insights page</p>} />
            <Route path="/import" element={<p>Import page</p>} />
          </Routes>
        </CommandBarProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.keyDown(window, { key: "k", metaKey: true });
  return screen.findByRole("combobox", { name: "Search or add" });
}

afterEach(() => vi.restoreAllMocks());

describe("CommandBar", () => {
  it("finds in your library first and opens what you choose", async () => {
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        if (url.startsWith("/api/search/library"))
          return new Response(JSON.stringify([entry]));
        if (url.startsWith("/api/search?"))
          return new Response(JSON.stringify([candidate]));
        return new Response("[]");
      });
    const input = await renderBar();
    await userEvent.type(input, "rayuela");
    const hit = await screen.findByRole("option", { name: /Rayuela/ });
    expect(
      fetch.mock.calls.some(
        ([url]) => String(url) === "/api/search/library?q=rayuela",
      ),
    ).toBe(true);
    await userEvent.click(hit);
    expect(await screen.findByText("Detail page")).toBeInTheDocument();
  });

  it("adds a web result with the domain's default status, without leaving the page", async () => {
    const posts: unknown[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/entries" && init?.method === "POST") {
        posts.push(JSON.parse(String(init.body)));
        return new Response(
          JSON.stringify({
            entry: { ...entry, id: 8 },
            already_exists: false,
            near_matches: [],
          }),
          { status: 201 },
        );
      }
      if (url.startsWith("/api/search/library")) return new Response("[]");
      if (url.startsWith("/api/search?"))
        return new Response(JSON.stringify([candidate]));
      return new Response("[]");
    });
    const input = await renderBar();
    await userEvent.type(input, "ficciones");
    await userEvent.click(
      await screen.findByRole("option", { name: /Ficciones/ }),
    );
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]).toMatchObject({
      source: "openlibrary",
      source_id: "OL1M",
    });
    expect(posts[0]).not.toHaveProperty("status");
    expect(await screen.findByText(/Added · Open/)).toBeInTheDocument();
    expect(screen.getByText("Library page")).toBeInTheDocument();
  });

  it("resolves a pasted link instead of searching for it", async () => {
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        if (String(input).startsWith("/api/search/resolve"))
          return new Response(JSON.stringify([candidate]));
        return new Response("[]");
      });
    const input = await renderBar();
    await userEvent.click(input);
    await userEvent.paste("https://openlibrary.org/works/OL1W");
    expect(await screen.findByText("From that link")).toBeInTheDocument();
    expect(
      await screen.findByRole("option", { name: /Ficciones/ }),
    ).toBeInTheDocument();
    expect(
      fetch.mock.calls.some(([url]) =>
        String(url).startsWith("/api/search/library"),
      ),
    ).toBe(false);
  });

  it("goes places by name", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response("[]"),
    );
    const input = await renderBar();
    await userEvent.type(input, "insights");
    await userEvent.keyboard("{Enter}");
    expect(await screen.findByText("Insights page")).toBeInTheDocument();
  });
});

describe("paste and drop anywhere", () => {
  function mount() {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/"]}>
          <CommandBarProvider>
            <Routes>
              <Route path="/" element={<p>Library page</p>} />
              <Route path="/import" element={<p>Import page</p>} />
            </Routes>
          </CommandBarProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("opens the bar resolving a link pasted outside a field", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response("[]"),
    );
    mount();
    const paste = new Event("paste", { bubbles: true }) as Event & {
      clipboardData: { getData: () => string };
    };
    paste.clipboardData = { getData: () => "imdb.com/title/tt0111161" };
    fireEvent(document.body, paste);
    expect(
      await screen.findByRole("combobox", { name: "Search or add" }),
    ).toHaveValue("imdb.com/title/tt0111161");
  });

  it("hands a dropped export to the importer that claims it", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/import/detect")
        return new Response(
          JSON.stringify({
            files: [
              {
                name: "goodreads.csv",
                matches: [{ importer: "goodreads", confidence: 0.95 }],
              },
            ],
          }),
        );
      return new Response("[]");
    });
    mount();
    const file = new File(["Book Id,Title,Author"], "goodreads.csv", {
      type: "text/csv",
    });
    const dataTransfer = { types: ["Files"], files: [file] };
    fireEvent(window, Object.assign(new Event("dragenter"), { dataTransfer }));
    expect(screen.getByTestId("drop-veil")).toBeInTheDocument();
    fireEvent(
      window,
      Object.assign(new Event("drop", { cancelable: true }), { dataTransfer }),
    );
    expect(await screen.findByText("Import page")).toBeInTheDocument();
    expect(takeHandedFiles("goodreads")).toEqual([file]);
  });
});
