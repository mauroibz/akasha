import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { findToast } from "@/test/toast";
import { HomePage } from "./HomePage";

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderPage(initialEntry = "/", client = makeClient()) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/books/:entryId" element={<h1>Book detail</h1>} />
          <Route path="/triage" element={<h1>Triage</h1>} />
        </Routes>
        <Toaster />
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
        creator: "Cortázar, Julio",
        cover_path: null,
        cover_url: null,
        metadata: {},
        identifiers: {},
        sources: [],
      },
      shelves: [],
      formats: [],
    },
  ],
  next_cursor: null,
  total: 1,
  facets: {
    status_counts: { read: 1, unsorted: 12 },
    status_counts_by_type: {},
    format_counts: {},
  },
};

test("announces loading and then renders the populated library and inbox facet", async () => {
  let resolveResponse: ((response: Response) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((request: string | URL | Request) => {
      // The page also loads the shelf list; only the library request is held open.
      if (String(request).startsWith("/api/item-types")) {
        return new Response("[]");
      }
      if (String(request).startsWith("/api/item-types")) {
        return new Response("[]");
      }
      if (String(request).startsWith("/api/shelves")) {
        return Promise.resolve(new Response("[]", { status: 200 }));
      }
      return new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      });
    }),
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
            facets: {
              status_counts: { unsorted: 3 },
              status_counts_by_type: {},
              format_counts: {},
            },
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

test("abandons the in-flight page when the sort changes again", async () => {
  // Changing sort abandons the previous query key. Without a signal reaching
  // `fetch`, the browser kept downloading a page nobody would ever render,
  // holding one of six connections while the reader kept adjusting filters
  // (technical spec section 8).
  const signals: AbortSignal[] = [];
  let hang = false;
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input, init) =>
      new Promise<Response>((resolve) => {
        if (!String(input).startsWith("/api/entries")) {
          return resolve(new Response("[]", { status: 200 }));
        }
        signals.push(init!.signal as AbortSignal);
        // Only the sort-triggered fetches are left open; the first has to
        // land or there is no page to interact with.
        if (hang) return;
        resolve(new Response(JSON.stringify(populated), { status: 200 }));
      }),
  );
  renderPage();
  await screen.findByText("Rayuela");
  hang = true;

  const user = userEvent.setup();
  const chooseSort = async (name: string) => {
    await user.click(screen.getByRole("combobox", { name: /sort library/i }));
    await user.click(await screen.findByRole("option", { name }));
  };
  await chooseSort("Score ↓");
  await waitFor(() => expect(signals).toHaveLength(2));
  await chooseSort("Score ↑");
  await waitFor(() => expect(signals).toHaveLength(3));

  expect(signals[1].aborted).toBe(true);
  expect(signals[2].aborted).toBe(false);
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
  // Both densities are a feed of articles. The compact view used to claim
  // `role="table"` over rows that contained no cells (DEC-038), so what is
  // asserted here is the preference and the density, not a table.
  expect(screen.getByRole("feed", { name: "Library" })).toBeVisible();
  expect(screen.getByRole("article", { name: "Rayuela" }).className).toContain(
    "items-center",
  );
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
  expect(await findToast(/previous value was restored/)).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /score for rayuela: 9/i }),
  ).toBeVisible();
  // The toast names no book. The marker is what says which row reverted, and
  // it is visual state only -- no text, no role, no second live region, so the
  // confirmation is still announced exactly once (DEC-028).
  await waitFor(() => expect(row).toHaveAttribute("data-rollback", "true"));
  expect(row?.className).toContain("animate-shake");
});

test("the rollback restores the query key it snapshotted, not the one on screen", async () => {
  // The snapshot is taken against the key that was active when the write
  // started. Restoring it into whatever key the component happens to be
  // rendering when the write fails writes one sort's list into another sort's
  // cache -- input silently lost, which technical spec section 8 forbids.
  let rejectPatch: ((reason?: unknown) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((request: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "PATCH")
        return new Promise<Response>((_resolve, reject) => {
          rejectPatch = reject;
        });
      return Promise.resolve(
        new Response(JSON.stringify(populated), { status: 200 }),
      );
    }),
  );
  const client = makeClient();
  renderPage("/", client);
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: /score for rayuela: 9/i }),
  );
  await user.click(screen.getByRole("button", { name: "Score 4" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: /score for rayuela: 4/i }),
    ).toBeVisible(),
  );

  await user.click(screen.getByRole("combobox", { name: "Sort library" }));
  await user.click(screen.getByRole("option", { name: /Score ↓/ }));
  await waitFor(() =>
    expect(
      screen.getByRole("combobox", { name: "Sort library" }),
    ).toHaveTextContent(/Score/),
  );

  const writes = vi.spyOn(client, "setQueryData");
  rejectPatch?.(new Error("offline"));
  expect(await findToast(/previous value was restored/)).toBeInTheDocument();
  const restored = writes.mock.calls.map(
    ([key]) => key as [string, { sort: string }],
  );
  expect(restored.length).toBeGreaterThan(0);
  for (const [, filters] of restored) expect(filters.sort).toBe("date_added");
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
  await screen.findByText("Triage");
});

test("the shelf filter lists every shelf, not only those on loaded pages", async () => {
  // No loaded entry carries a shelf, so a filter derived from `entries` is empty.
  const fetchMock = vi.fn(async (request: string | URL | Request) => {
    if (String(request).startsWith("/api/item-types")) {
      return new Response("[]");
    }
    if (String(request).startsWith("/api/shelves")) {
      return new Response(
        JSON.stringify([
          { id: 3, name: "Ensayo", slug: "ensayo", entry_count: 12 },
          { id: 1, name: "Argentina", slug: "argentina", entry_count: 40 },
        ]),
        { status: 200 },
      );
    }
    return new Response(JSON.stringify(populated), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderPage();
  await screen.findByText("Rayuela");

  // Radix renders the trigger as button[role="combobox"] and portals the
  // listbox to document.body, so the options only exist once it is opened.
  const filter = screen.getByRole("combobox", { name: "Filter by shelf" });
  const user = userEvent.setup();
  await user.click(filter);
  const listbox = await screen.findByRole("listbox");
  expect(
    within(listbox).getByRole("option", { name: "Argentina" }),
  ).toBeInTheDocument();
  expect(
    within(listbox).getByRole("option", { name: "Ensayo" }),
  ).toBeInTheDocument();
  // Alphabetical, regardless of the order the endpoint returned.
  expect(
    within(listbox)
      .getAllByRole("option")
      .map((option) => option.textContent),
  ).toEqual(["All shelves", "Argentina", "Ensayo"]);
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

/**
 * Three domains, one of which this build has never heard of.
 *
 * The point of the third is that no hardcoded list could produce it: if the strip
 * renders "Wines", it renders from `/api/item-types` and not from a table beside it.
 */
const threeDomains = [
  {
    id: "book",
    label: "Book",
    fields: [],
    statuses: [
      { value: "read", label: "Read", choosable: true, hotkey: "r" },
      { value: "reading", label: "Reading", choosable: true, hotkey: "g" },
    ],
    default_status: "read",
    entry_fields: ["date_started", "date_finished", "reread_count"],
    formats: [
      { value: "physical", label: "Physical" },
      { value: "digital", label: "Digital" },
    ],
    entry_panel_label: "Your reading data",
  },
  {
    id: "album",
    label: "Record",
    fields: [],
    statuses: [
      { value: "owned", label: "Owned", choosable: true, hotkey: "o" },
    ],
    default_status: "owned",
    entry_fields: [],
    formats: [
      { value: "vinyl", label: "Vinyl" },
      { value: "digital", label: "Digital" },
    ],
    entry_panel_label: "Your copy",
  },
  {
    id: "wine",
    label: "Wine",
    fields: [],
    statuses: [
      { value: "owned", label: "Owned", choosable: true, hotkey: "o" },
    ],
    default_status: "owned",
    entry_fields: [],
    formats: [{ value: "physical", label: "Bottle" }],
    entry_panel_label: "Your cellar",
  },
];

function stubRegistry(page = populated) {
  const fetchMock = vi.fn(async (request: string | URL | Request) => {
    if (String(request).startsWith("/api/item-types"))
      return new Response(JSON.stringify(threeDomains));
    if (String(request).startsWith("/api/shelves")) return new Response("[]");
    return new Response(JSON.stringify(page), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function requestedUrls(fetchMock: ReturnType<typeof stubRegistry>): string[] {
  return fetchMock.mock.calls.map((call) => String(call[0]));
}

test("the domain tab strip is built from the registry, not from a hardcoded list", async () => {
  const fetchMock = stubRegistry();
  renderPage();
  await screen.findByText("Rayuela");

  const strip = await screen.findByRole("radiogroup", {
    name: "Choose a domain",
  });
  expect(
    within(strip)
      .getAllByRole("radio")
      .map((tab) => tab.textContent),
  ).toEqual(["All", "Book", "Record", "Wine"]);
  // Nothing has been chosen, so the library is unfiltered.
  expect(requestedUrls(fetchMock).some((url) => url.includes("type="))).toBe(
    false,
  );
});

test("choosing a domain filters the library, and the choice is in the URL", async () => {
  const fetchMock = stubRegistry();
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.click(screen.getByRole("radio", { name: "Record" }));

  await waitFor(() => {
    expect(
      requestedUrls(fetchMock).some(
        (url) => url.startsWith("/api/entries?") && url.includes("type=album"),
      ),
    ).toBe(true);
  });
  // In the URL like every other filter, which is what makes a reload and the back
  // button work without the page owning any of that itself.
  expect(screen.getByRole("radio", { name: "Record" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
});

test("the last domain used is where a fresh visit lands", async () => {
  localStorage.setItem("akasha.library.domain", "album");
  const fetchMock = stubRegistry();
  renderPage();
  await screen.findByText("Rayuela");

  await waitFor(() => {
    expect(
      requestedUrls(fetchMock).some(
        (url) => url.startsWith("/api/entries?") && url.includes("type=album"),
      ),
    ).toBe(true);
  });
  expect(screen.getByRole("radio", { name: "Record" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
});

test("a type already in the URL beats the remembered domain", async () => {
  localStorage.setItem("akasha.library.domain", "album");
  const fetchMock = stubRegistry();
  renderPage("/?type=book");
  await screen.findByText("Rayuela");

  await waitFor(() => {
    expect(
      requestedUrls(fetchMock).some(
        (url) => url.startsWith("/api/entries?") && url.includes("type=book"),
      ),
    ).toBe(true);
  });
  expect(
    requestedUrls(fetchMock).some((url) => url.includes("type=album")),
  ).toBe(false);
});

test("with a domain chosen, only that domain's status chips and formats render", async () => {
  stubRegistry();
  renderPage("/?type=album");
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  // The record row, without the domain heading the tab already carries.
  expect(screen.getByRole("button", { name: /^Owned/ })).toBeVisible();
  expect(screen.queryByRole("button", { name: /^Read / })).toBeNull();
  expect(screen.queryByRole("button", { name: /^Reading/ })).toBeNull();

  // And the format selector narrows to that domain's vocabulary.
  await user.click(screen.getByRole("combobox", { name: "Filter by format" }));
  const listbox = await screen.findByRole("listbox");
  expect(
    within(listbox)
      .getAllByRole("option")
      .map((option) => option.textContent?.replace(/\s+\d+$/, "")),
  ).toEqual(["All formats", "Vinyl", "Digital"]);
});

test("switching domain drops a status the new domain has no vocabulary for", async () => {
  const fetchMock = stubRegistry();
  renderPage("/?type=book&status=reading");
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.click(screen.getByRole("radio", { name: "Record" }));

  // Otherwise the list stays filtered to a status the visible chips cannot clear,
  // and the library reads as empty for no reason the screen can explain.
  await waitFor(() => {
    const last = requestedUrls(fetchMock).at(-1)!;
    expect(last).toContain("type=album");
    expect(last).not.toContain("status=reading");
  });
});
