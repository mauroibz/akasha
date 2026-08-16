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
          <Route path="/add" element={<h1>Add page</h1>} />
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
  // The list request now waits for `/api/item-types`, because every list request
  // names a domain and on a cold visit the registry is where that name comes from.
  // So the response cannot be resolved until the request has actually been made.
  await waitFor(() => expect(resolveResponse).toBeDefined());
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
  const search = screen.getByRole("searchbox", {
    name: "Search your library, or add something new",
  });
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
  ).toEqual(["Book", "Record", "Wine"]);
  // The strip always names exactly one domain (DEC-065), so with nothing
  // remembered the library is filtered to the first declared one rather than
  // showing everything.
  await waitFor(() => {
    expect(
      requestedUrls(fetchMock).some(
        (url) => url.startsWith("/api/entries?") && url.includes("type=book"),
      ),
    ).toBe(true);
  });
});

test("nothing remembered lands on the first declared domain, and there is no way back to All", async () => {
  const fetchMock = stubRegistry();
  renderPage();
  await screen.findByText("Rayuela");

  const strip = await screen.findByRole("radiogroup", {
    name: "Choose a domain",
  });
  // "All" is gone as a control, not merely as a default: there is no way to
  // express a library filtered by no domain at all.
  expect(within(strip).queryByRole("radio", { name: "All" })).toBeNull();
  expect(screen.getByRole("radio", { name: "Book" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
  // And every library request names a domain.
  const libraryUrls = requestedUrls(fetchMock).filter((url) =>
    url.startsWith("/api/entries?"),
  );
  expect(libraryUrls.length).toBeGreaterThan(0);
  expect(libraryUrls.every((url) => url.includes("type="))).toBe(true);
});

test("a stored empty preference resolves to the first declared domain", async () => {
  // Sprint 027 stored "" as the way of saying "All". That filter no longer
  // exists, and `readDomainPreference` also returns "" for a first-ever visit,
  // so one branch has to cover both.
  localStorage.setItem("akasha.library.domain", "");
  const fetchMock = stubRegistry();
  renderPage();
  await screen.findByText("Rayuela");

  await waitFor(() => {
    expect(
      requestedUrls(fetchMock).some(
        (url) => url.startsWith("/api/entries?") && url.includes("type=book"),
      ),
    ).toBe(true);
  });
  expect(
    requestedUrls(fetchMock).some(
      (url) => url.startsWith("/api/entries?") && !url.includes("type="),
    ),
  ).toBe(false);
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

/* ------------------------------------------------------------------ *
 * Sprint 029 — one bar: the library first, a provider only on a miss.
 * ------------------------------------------------------------------ */

const empty = {
  items: [],
  next_cursor: null,
  total: 0,
  facets: {
    status_counts: { unsorted: 0 },
    status_counts_by_type: {},
    format_counts: {},
  },
};

const candidate = {
  source: "openlibrary",
  source_id: "OL1M",
  source_refs: [{ source: "openlibrary", source_id: "OL1M" }],
  title: "Dune Messiah",
  subtitle: null,
  creators: ["Frank Herbert"],
  credit: "Frank Herbert",
  year: 1969,
  cover_url: null,
  identifiers: {},
  language: "en",
  metadata: {},
};

/**
 * The whole point of the bar is which requests it does and does not make, so the
 * stub records every URL and the tests count them.
 */
interface BarStub {
  libraryHasRows?: boolean;
  /** Answer provider search with a failure instead of a result set. */
  searchFails?: boolean;
  health?: unknown;
  /** What `POST /api/entries` answers. */
  onCreate?: (body: unknown) => Response;
  onPreview?: () => Response;
}

function stubBar(options: BarStub = {}) {
  const { libraryHasRows = true } = options;
  const urls: string[] = [];
  const posts: unknown[] = [];
  const signals: AbortSignal[] = [];
  const fetchMock = vi.fn(
    async (request: string | URL | Request, init?: RequestInit) => {
      const url = String(request);
      urls.push(url);
      if (url.startsWith("/api/item-types"))
        return new Response(JSON.stringify(threeDomains));
      if (url.startsWith("/api/shelves")) return new Response("[]");
      if (url.startsWith("/api/health/providers"))
        return new Response(
          JSON.stringify(options.health ?? { providers: [], degraded: false }),
        );
      if (url.startsWith("/api/search/preview"))
        return options.onPreview?.() ?? new Response(JSON.stringify(candidate));
      if (url.startsWith("/api/search")) {
        if (init?.signal) signals.push(init.signal);
        return options.searchFails
          ? new Response("upstream is down", { status: 502 })
          : new Response(JSON.stringify([candidate]));
      }
      if (init?.method === "POST" && url === "/api/entries") {
        const body: unknown = JSON.parse(String(init.body));
        posts.push(body);
        return (
          options.onCreate?.(body) ??
          new Response(
            JSON.stringify({
              entry: { ...populated.items[0], id: 42 },
              already_exists: false,
              near_matches: [],
            }),
            { status: 201 },
          )
        );
      }
      // The library. A query in the URL is the "did you already own it" question.
      const hasQuery = url.includes("q=");
      return new Response(
        JSON.stringify(hasQuery && !libraryHasRows ? empty : populated),
        { status: 200 },
      );
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return {
    urls,
    posts,
    signals,
    providerCalls: () =>
      urls.filter((u) => u.startsWith("/api/search") && !u.includes("preview")),
  };
}

/** Type a miss, wait for the one search it costs, and open the confirm dialog. */
async function openConfirmDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByRole("searchbox"), "Dune Messiah");
  const result = await screen.findByRole(
    "button",
    { name: /Dune Messiah/ },
    { timeout: 3000 },
  );
  await user.click(result);
  return screen.findByRole("dialog");
}

const settle = (ms = 1400) => new Promise((r) => setTimeout(r, ms));

test("a library hit reaches no provider, however long the query gets", async () => {
  const bar = stubBar({ libraryHasRows: true });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.type(await screen.findByRole("searchbox"), "Rayuela");
  await settle();

  // AC1. Not "few requests" — none. The library answering is the whole reason
  // this bar can be one bar.
  expect(bar.providerCalls()).toEqual([]);
});

test("a settled query with nothing local reaches a provider exactly once", async () => {
  const bar = stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.type(await screen.findByRole("searchbox"), "Dune Messiah");
  await waitFor(() => expect(bar.providerCalls().length).toBe(1), {
    timeout: 3000,
  });
  await settle();

  // AC2, counted rather than eyeballed: typing twelve characters costs one
  // search, not twelve (DEC-065, and DEC-044 for why that matters).
  expect(bar.providerCalls().length).toBe(1);
  expect(await screen.findByText("Dune Messiah")).toBeVisible();
});

test("the same query typed again reaches no provider at all", async () => {
  const bar = stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const box = await screen.findByRole("searchbox");

  await user.type(box, "Dune Messiah");
  await waitFor(() => expect(bar.providerCalls().length).toBe(1), {
    timeout: 3000,
  });
  await user.clear(box);
  await user.type(box, "Dune Messiah");
  await settle();

  expect(bar.providerCalls().length).toBe(1);
});

test("Add searches immediately even when the library has the answer", async () => {
  const bar = stubBar({ libraryHasRows: true });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.type(await screen.findByRole("searchbox"), "Rayuela");
  await settle();
  expect(bar.providerCalls()).toEqual([]);

  // AC3: the override for "I know this is a different edition".
  await user.click(screen.getByRole("button", { name: "Add" }));
  await waitFor(() => expect(bar.providerCalls().length).toBe(1));
  expect(bar.providerCalls()[0]).toContain("/api/search?");
});

test("a pasted ISBN and a pasted URL both take the resolve route", async () => {
  const bar = stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const box = await screen.findByRole("searchbox");

  await user.type(box, "9780441013593");
  await user.click(screen.getByRole("button", { name: "Add" }));
  await waitFor(() => expect(bar.providerCalls().length).toBe(1));
  expect(bar.providerCalls()[0]).toContain("/api/search/resolve?url=");

  await user.clear(box);
  await user.type(box, "https://openlibrary.org/books/OL1M");
  await user.click(screen.getByRole("button", { name: "Add" }));
  await waitFor(() => expect(bar.providerCalls().length).toBe(2));
  expect(bar.providerCalls()[1]).toContain("/api/search/resolve?url=");
});

test("the domain chosen picks the providers as well as the rows", async () => {
  const bar = stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  // AC4: one action, both meanings, and never a moment where the application
  // would have to ask which domain a search means.
  await user.click(screen.getByRole("radio", { name: "Record" }));
  await user.type(await screen.findByRole("searchbox"), "Kind of Blue");
  await user.click(screen.getByRole("button", { name: "Add" }));

  await waitFor(() => expect(bar.providerCalls().length).toBe(1));
  expect(bar.providerCalls()[0]).toContain("type=album");
  expect(
    bar.urls.some((u) => u.includes("q=Kind") && u.includes("type=album")),
  ).toBe(true);
});

test("choosing a web result opens the confirm form over the library", async () => {
  stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.type(await screen.findByRole("searchbox"), "Dune Messiah");
  const result = await screen.findByRole(
    "button",
    { name: /Dune Messiah/ },
    { timeout: 3000 },
  );
  await user.click(result);

  const dialog = await screen.findByRole("dialog");
  // The confirm form entire, in a dialog, over a library that is still there.
  expect(
    within(dialog).getByRole("combobox", { name: /status/i }),
  ).toBeVisible();
  expect(
    within(dialog).getByRole("button", { name: /add to library/i }),
  ).toBeVisible();
});

/* ------------------------------------------------------------------ *
 * The functionality inventory (deliverable 4). Each row is the thing
 * the owner asked not to lose, demonstrated from `/` rather than /add.
 * ------------------------------------------------------------------ */

test("row 3+4: a degraded provider is announced, and a failed search offers the way past it", async () => {
  stubBar({
    libraryHasRows: false,
    searchFails: true,
    health: {
      providers: [{ name: "googlebooks", healthy: false, reason: "quota" }],
      degraded: true,
    },
  });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.type(await screen.findByRole("searchbox"), "Dune Messiah");
  // A failed search is a dead end unless it says so and offers a way past it.
  expect(
    await screen.findByRole("alert", {}, { timeout: 3000 }),
  ).toHaveTextContent(/providers are unavailable/i);
  expect(screen.getByRole("button", { name: /enter manually/i })).toBeVisible();
});

test("row 6: None of these leaves for the manual form", async () => {
  stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.type(await screen.findByRole("searchbox"), "Dune Messiah");
  await user.click(
    await screen.findByRole(
      "button",
      { name: /enter manually/i },
      { timeout: 3000 },
    ),
  );
  expect(
    await screen.findByRole("heading", { name: /add page/i }),
  ).toBeVisible();
});

test("row 7: the confirm form shows what the search already returned, and fetches the rest only when asked", async () => {
  const bar = stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const dialog = await openConfirmDialog(user);

  // Free data, immediately, with no second provider request (DEC-064).
  expect(within(dialog).getByText("Frank Herbert")).toBeVisible();
  expect(bar.urls.some((u) => u.includes("/api/search/preview"))).toBe(false);

  await user.click(
    within(dialog).getByRole("button", { name: /load full details/i }),
  );
  await waitFor(() =>
    expect(
      bar.urls.filter((u) => u.includes("/api/search/preview")),
    ).toHaveLength(1),
  );
  // Exactly once: the button goes once it has answered.
  expect(
    within(dialog).queryByRole("button", { name: /load full details/i }),
  ).toBeNull();
});

test("row 7: a failed preview says so and still lets you add", async () => {
  stubBar({
    libraryHasRows: false,
    onPreview: () => new Response("nope", { status: 502 }),
  });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const dialog = await openConfirmDialog(user);

  await user.click(
    within(dialog).getByRole("button", { name: /load full details/i }),
  );
  expect(await within(dialog).findByRole("alert")).toHaveTextContent(
    /could not be loaded/i,
  );
  expect(
    within(dialog).getByRole("button", { name: /add to library/i }),
  ).toBeEnabled();
});

test("row 8+9: a near match must be confirmed, and the confirmation takes focus", async () => {
  let posts = 0;
  const bar = stubBar({
    libraryHasRows: false,
    onCreate: () => {
      posts += 1;
      return posts === 1
        ? new Response(
            JSON.stringify({
              error: {
                code: "near_match_confirmation_required",
                details: { entry_ids: [7] },
              },
            }),
            { status: 409 },
          )
        : new Response(
            JSON.stringify({
              entry: { ...populated.items[0], id: 42 },
              already_exists: false,
              near_matches: [],
            }),
            { status: 201 },
          );
    },
  });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const dialog = await openConfirmDialog(user);

  await user.click(
    within(dialog).getByRole("button", { name: /add to library/i }),
  );
  const confirm = await within(dialog).findByRole("button", {
    name: /add separate edition/i,
  });
  // Row 9: the 409 puts focus on the button that resolves it.
  expect(confirm).toHaveFocus();
  expect(
    within(dialog).getByRole("button", { name: /open existing entry/i }),
  ).toBeVisible();

  await user.click(confirm);
  await waitFor(() => expect(bar.posts).toHaveLength(2));
  expect(
    (bar.posts[1] as { confirm_near_match?: boolean }).confirm_near_match,
  ).toBe(true);
});

test("row 9: choosing a result focuses the status control", async () => {
  stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const dialog = await openConfirmDialog(user);

  await waitFor(() =>
    expect(
      within(dialog).getByRole("combobox", { name: /status/i }),
    ).toHaveFocus(),
  );
});

test("row 10+11: an add that already exists opens it, and a new one is highlighted in place", async () => {
  const bar = stubBar({
    libraryHasRows: false,
    onCreate: () =>
      new Response(
        JSON.stringify({
          entry: { ...populated.items[0], id: 7 },
          already_exists: true,
          near_matches: [],
        }),
        { status: 200 },
      ),
  });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const dialog = await openConfirmDialog(user);

  await user.click(
    within(dialog).getByRole("button", { name: /add to library/i }),
  );
  expect(await findToast("Already in your library")).toBeInTheDocument();
  // Row 10: exactly one POST, and no second add behind the 200.
  expect(bar.posts).toHaveLength(1);
});

test("row 11: a successful add closes the dialog and stays on the library", async () => {
  stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const dialog = await openConfirmDialog(user);

  await user.click(
    within(dialog).getByRole("button", { name: /add to library/i }),
  );
  expect(await findToast("Book added")).toBeInTheDocument();
  // The handoff on `/` is a dialog closing, not a navigation.
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.queryByRole("heading", { name: /book detail/i })).toBeNull();
});

test("row 12+13: a superseded search is aborted, and a late response cannot land", async () => {
  const bar = stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();
  const box = await screen.findByRole("searchbox");

  // Two presses of Add for two different strings: the first request must be
  // cancelled rather than left running against a rate-limited free API.
  await user.type(box, "Dune Messiah");
  await user.click(screen.getByRole("button", { name: "Add" }));
  await waitFor(() => expect(bar.signals.length).toBe(1));
  await user.clear(box);
  await user.type(box, "Children of Dune");
  await user.click(screen.getByRole("button", { name: "Add" }));
  await waitFor(() => expect(bar.signals.length).toBe(2));

  expect(bar.signals[0].aborted).toBe(true);
  expect(bar.signals[1].aborted).toBe(false);
});

test("deliverable 6: adding a record says Record added, not Book added", async () => {
  // The guard on copy neutrality. Every string the add flow shows has to come
  // from the domain's own label, so this asserts the flow against the domain
  // that is *not* the default -- the one a hardcoded "Book" would get wrong.
  stubBar({ libraryHasRows: false });
  renderPage();
  await screen.findByText("Rayuela");
  const user = userEvent.setup();

  await user.click(screen.getByRole("radio", { name: "Record" }));
  const dialog = await openConfirmDialog(user);
  await user.click(
    within(dialog).getByRole("button", { name: /add to library/i }),
  );

  // Sonner's store is module-global and outlives a single test, so this asserts
  // the toast this add produced rather than scanning the document for the word.
  // A hardcoded "Book added" fails it by never producing the one named here.
  expect(await findToast("Record added")).toBeInTheDocument();
});
