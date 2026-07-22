import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { HomePage } from "./HomePage";

function renderPage(initialEntry = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/books/:entryId" element={<h1>Book detail</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

const populated = {
  items: [
    {
      id: 7,
      item_id: 9,
      status: "read",
      score: 9,
      notes: null,
      date_added: "2026-07-22T00:00:00Z",
      date_started: null,
      date_finished: null,
      reread_count: 0,
      score_provisional: false,
      suggested_status: null,
      item: {
        id: 9,
        type: "book",
        title: "Rayuela",
        subtitle: null,
        year: 1963,
        sort_author: "Cortázar, Julio",
        cover_path: null,
        cover_url: null,
        metadata: {},
        identifiers: {},
        sources: [],
      },
      shelves: [],
    },
  ],
  next_cursor: null,
  total: 1,
  facets: { status_counts: { read: 1, unsorted: 12 } },
};

test("announces loading and then renders the populated library and inbox facet", async () => {
  let resolveResponse: ((response: Response) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveResponse = resolve;
        }),
    ),
  );
  renderPage();
  expect(screen.getByRole("status")).toHaveTextContent("Loading your library");
  resolveResponse?.(new Response(JSON.stringify(populated), { status: 200 }));
  expect(await screen.findByText("Rayuela")).toBeVisible();
  expect(screen.getAllByText(/Inbox 12/)[0]).toBeVisible();
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/entries"),
    expect.anything(),
  );
});

test("renders a useful empty state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            items: [],
            next_cursor: null,
            total: 0,
            facets: { status_counts: { unsorted: 3 } },
          }),
          { status: 200 },
        ),
    ),
  );
  renderPage();
  expect(await screen.findByText("Your library is waiting")).toBeVisible();
  expect(screen.getAllByText(/Inbox 3/)[0]).toBeVisible();
});

test("announces a library error and offers retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("", { status: 503 })),
  );
  renderPage();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Your library could not be loaded",
  );
  expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("persists the compact table preference", async () => {
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(populated), { status: 200 })),
  );
  renderPage();
  const user = userEvent.setup();
  await screen.findByText("Rayuela");
  await user.click(screen.getByRole("button", { name: "Table view" }));
  expect(localStorage.getItem("akasha.library.view")).toBe("table");
  expect(screen.getByRole("table", { name: "Library" })).toBeVisible();
});

test("optimistically clears provisional score styling and rolls back with an announcement", async () => {
  const provisional = {
    ...populated,
    items: [{ ...populated.items[0], score_provisional: true }],
  };
  let rejectPatch: ((reason?: unknown) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((request: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return new Promise<Response>((_resolve, reject) => {
          rejectPatch = reject;
        });
      }
      return Promise.resolve(
        new Response(JSON.stringify(provisional), { status: 200 }),
      );
    }),
  );
  renderPage();
  const user = userEvent.setup();
  const scoreButton = await screen.findByRole("button", {
    name: /score for rayuela: 9/i,
  });
  const row = scoreButton.closest("article");
  expect(row).toHaveAttribute("data-provisional", "true");
  await user.click(scoreButton);
  await user.click(screen.getByRole("button", { name: "Score 7" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: /score for rayuela: 7/i }),
    ).toBeVisible(),
  );
  expect(row).toHaveAttribute("data-provisional", "false");
  rejectPatch?.(new Error("offline"));
  expect(
    await screen.findByText(/previous value was restored/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /score for rayuela: 9/i }),
  ).toBeVisible();
});

test("score shortcuts apply to a focused row but editable controls keep their keystrokes", async () => {
  const fetchMock = vi.fn(
    async (request: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return new Response(
          JSON.stringify({ ...populated.items[0], score: 5 }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify(populated), { status: 200 });
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  renderPage();
  const user = userEvent.setup();
  const row = await screen.findByRole("article", { name: "Rayuela" });
  act(() => row.focus());
  await user.keyboard("5");
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/entries/7",
    expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify({ score: 5 }),
    }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: /score for rayuela: 5/i }),
    ).toBeVisible(),
  );
  const search = screen.getByRole("searchbox", { name: "Search library" });
  await user.click(search);
  await user.keyboard("a");
  expect(search).toHaveValue("a");
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("q=a"),
      expect.anything(),
    ),
  );
});

test("Inbox count applies the unsorted filter", async () => {
  const fetchMock = vi.fn(
    async (request: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return new Response(JSON.stringify(populated.items[0]), {
          status: 200,
        });
      }
      return new Response(JSON.stringify(populated), { status: 200 });
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  renderPage();
  const user = userEvent.setup();
  await screen.findByText("Rayuela");
  const inboxButtons = screen.getAllByRole("button", { name: /inbox 12/i });
  await user.click(inboxButtons[0]);
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("status=unsorted"),
      expect.anything(),
    ),
  );
});

test("a library row opens detail by pointer", async () => {
  const fetchMock = vi.fn(
    async (request: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return new Response(JSON.stringify(populated.items[0]), {
          status: 200,
        });
      }
      return new Response(JSON.stringify(populated), { status: 200 });
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  renderPage();
  const user = userEvent.setup();
  await screen.findByText("Rayuela");
  // Click on the title heading to navigate (not the inline controls)
  const title = screen.getByText("Rayuela");
  await user.click(title);
  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Book detail" })).toBeVisible();
  });
});

test("Enter opens a focused row to detail", async () => {
  const fetchMock = vi.fn(
    async (request: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return new Response(JSON.stringify(populated.items[0]), {
          status: 200,
        });
      }
      return new Response(JSON.stringify(populated), { status: 200 });
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  renderPage();
  const user = userEvent.setup();
  const row = await screen.findByRole("article", { name: "Rayuela" });
  act(() => row.focus());
  await user.keyboard("{Enter}");
  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Book detail" })).toBeVisible();
  });
});
