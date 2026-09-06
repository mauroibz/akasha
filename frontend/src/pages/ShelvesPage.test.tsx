import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { ShelvesPage } from "./ShelvesPage";

const bookType = {
  id: "book",
  label: "Book",
  fields: [],
  statuses: [],
  default_status: "read",
  entry_fields: [],
  formats: [],
  entry_panel_label: "Your reading data",
};

const albumType = { ...bookType, id: "album", label: "Album" };

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ShelvesPage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const shelves = [
  {
    id: 1,
    name: "Favorites",
    slug: "favorites",
    entry_count: 5,
    covers: [],
    members_by_type: { book: 5 },
  },
  {
    id: 2,
    name: "Sci-fi",
    slug: "sci-fi",
    entry_count: 3,
    covers: [],
    members_by_type: { book: 3 },
  },
];

function stubApi(rows: unknown[] = shelves, types: unknown[] = [bookType]) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === "/api/item-types") return new Response(JSON.stringify(types));
    if (url === "/api/shelves") return new Response(JSON.stringify(rows));
    if (init?.method === "POST" && url === "/api/shelves")
      return new Response(JSON.stringify({ id: 3, name: "New", slug: "new" }));
    return new Response("[]");
  });
}

describe("ShelvesPage", () => {
  it("lists shelves as board cards with entry counts", async () => {
    stubApi();
    renderPage();
    expect(await screen.findByText("Favorites")).toBeVisible();
    // A shelf spans domains and always did, so it counts items rather than
    // naming one domain's noun (Sprint 029 deliverable 6).
    expect(screen.getByText("5 items")).toBeVisible();
    expect(screen.getByText("Sci-fi")).toBeVisible();
    expect(screen.getByText("3 items")).toBeVisible();
  });

  it("creates a shelf and refreshes the board", async () => {
    let created = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify([bookType]));
      if (init?.method === "POST" && url === "/api/shelves") {
        created = true;
        return new Response(
          JSON.stringify({ id: 3, name: "New", slug: "new", entry_count: 0 }),
          { status: 201 },
        );
      }
      if (url === "/api/shelves")
        return new Response(
          JSON.stringify(
            created
              ? [
                  ...shelves,
                  { id: 3, name: "New", slug: "new", entry_count: 0 },
                ]
              : shelves,
          ),
        );
      return new Response("[]");
    });
    renderPage();
    await screen.findByText("Favorites");
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/new shelf name/i), "New");
    await user.click(screen.getByRole("button", { name: /create shelf/i }));
    await waitFor(() => expect(screen.getByText("New")).toBeVisible());
  });

  it("a shelf card links into its own page", async () => {
    stubApi();
    renderPage();
    const link = await screen.findByRole("link", { name: /Favorites/ });
    expect(link).toHaveAttribute("href", "/shelves/favorites");
  });

  it("renders one magnitude bar per card, proportional to shelf size", async () => {
    stubApi([
      {
        id: 1,
        name: "Big",
        slug: "big",
        entry_count: 30,
        covers: [],
        members_by_type: { book: 30 },
      },
      {
        id: 2,
        name: "Small",
        slug: "small",
        entry_count: 10,
        covers: [],
        members_by_type: { book: 10 },
      },
    ]);
    renderPage();
    await screen.findByText("Big");
    const bars = document.querySelectorAll("[data-magnitude]");
    expect(bars).toHaveLength(2);
    const magnitudes = Array.from(bars).map((bar) =>
      bar.getAttribute("data-magnitude"),
    );
    // 30 is the leader: its own share is 1; 10 is a third of it.
    expect(magnitudes).toEqual(["1", "0.333"]);
    for (const bar of bars) {
      expect(bar).toHaveAttribute("aria-hidden", "true");
    }
  });

  it("gives a shelf's count visible weight against the largest shelf", async () => {
    stubApi([
      {
        id: 1,
        name: "Big",
        slug: "big",
        entry_count: 30,
        covers: [],
        members_by_type: { book: 30 },
      },
      {
        id: 2,
        name: "Small",
        slug: "small",
        entry_count: 1,
        covers: [],
        members_by_type: { book: 1 },
      },
    ]);
    renderPage();
    const bigCount = await screen.findByText("30 items");
    const smallCount = await screen.findByText("1 item");
    expect(bigCount.className).toContain("font-semibold");
    expect(smallCount.className).toContain("text-muted-foreground");
    expect(bigCount.className).not.toEqual(smallCount.className);
  });

  it("shows a rail of covers, the shared placeholder, or nothing for an empty shelf", async () => {
    stubApi([
      {
        id: 1,
        name: "Covered",
        slug: "covered",
        entry_count: 2,
        covers: ["/api/items/1/cover?v=1", "/api/items/2/cover?v=1"],
        members_by_type: { book: 2 },
      },
      {
        id: 2,
        name: "Coverless",
        slug: "coverless",
        entry_count: 3,
        covers: [],
        members_by_type: { book: 3 },
      },
      {
        id: 3,
        name: "Unstarted",
        slug: "unstarted",
        entry_count: 0,
        covers: [],
        members_by_type: {},
      },
    ]);
    renderPage();
    const coveredCard = (await screen.findByText("Covered")).closest("a");
    expect(coveredCard).not.toBeNull();
    // Decorative like the ranking's own `CoverStack` (empty `alt`), so these
    // are real `<img>` elements rather than accessible-role ones.
    expect((coveredCard as HTMLElement).querySelectorAll("img")).toHaveLength(
      2,
    );

    const coverlessCard = screen.getByText("Coverless").closest("a");
    expect(coverlessCard).not.toBeNull();
    expect(
      within(coverlessCard as HTMLElement).getByRole("img", {
        name: "No cover",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("3 items")).toBeVisible();

    const emptyCard = screen.getByText("Unstarted").closest("a");
    expect(emptyCard).not.toBeNull();
    expect(
      within(emptyCard as HTMLElement).queryByRole("img"),
    ).not.toBeInTheDocument();
    expect(within(emptyCard as HTMLElement).getByText("Empty")).toBeVisible();
  });

  it("shows one chip per domain a shelf holds, and they sum to its total", async () => {
    stubApi(
      [
        {
          id: 1,
          name: "Mixed",
          slug: "mixed",
          entry_count: 8,
          covers: [],
          members_by_type: { book: 5, album: 3 },
        },
      ],
      [bookType, albumType],
    );
    renderPage();
    const card = (await screen.findByText("Mixed")).closest("a") as HTMLElement;
    expect(within(card).getByText("Book 5")).toBeVisible();
    expect(within(card).getByText("Album 3")).toBeVisible();
  });

  it("shows exactly one chip for a single-domain shelf", async () => {
    stubApi();
    renderPage();
    const card = (await screen.findByText("Favorites")).closest(
      "a",
    ) as HTMLElement;
    expect(card.querySelectorAll("li")).toHaveLength(1);
  });

  it("the domain filter narrows the board and re-counts the cards", async () => {
    stubApi(
      [
        {
          id: 1,
          name: "Books only",
          slug: "books-only",
          entry_count: 5,
          covers: [],
          members_by_type: { book: 5 },
        },
        {
          id: 2,
          name: "Mixed",
          slug: "mixed",
          entry_count: 8,
          covers: [],
          members_by_type: { book: 5, album: 3 },
        },
      ],
      [bookType, albumType],
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Books only");
    expect(screen.getByText("Mixed")).toBeVisible();

    await user.click(screen.getByRole("radio", { name: "Album" }));

    expect(screen.queryByText("Books only")).not.toBeInTheDocument();
    expect(screen.getByText("Mixed")).toBeVisible();
    // Recounted to the chosen domain's members only (deliverable 3).
    const card = screen.getByText("Mixed").closest("a") as HTMLElement;
    expect(within(card).getByText("3 items")).toBeVisible();

    await user.click(screen.getByRole("radio", { name: "All" }));
    expect(screen.getByText("Books only")).toBeVisible();
  });

  it("sorts by size (default), by name, and by recently added", async () => {
    stubApi([
      {
        id: 1,
        name: "Zeta",
        slug: "zeta",
        entry_count: 1,
        covers: [],
        members_by_type: { book: 1 },
        updated_at: "2026-09-01T00:00:00Z",
      },
      {
        id: 2,
        name: "Alpha",
        slug: "alpha",
        entry_count: 9,
        covers: [],
        members_by_type: { book: 9 },
        updated_at: "2026-09-05T00:00:00Z",
      },
    ]);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Zeta");

    const names = () =>
      [...document.querySelectorAll("[data-shelf-name]")].map(
        (node) => node.textContent,
      );

    // Largest first by default.
    expect(names()[0]).toBe("Alpha");

    await user.click(screen.getByRole("button", { name: "Name" }));
    expect(names()[0]).toBe("Alpha");
    expect(names()[1]).toBe("Zeta");

    await user.click(screen.getByRole("button", { name: "Recently added" }));
    expect(names()[0]).toBe("Alpha");
  });

  it("surfaces duplicate slug errors", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify([bookType]));
      if (init?.method === "POST" && url === "/api/shelves")
        return new Response(
          JSON.stringify({
            error: {
              code: "shelf_slug_conflict",
              message: "Shelf name is already in use",
            },
          }),
          { status: 409 },
        );
      if (url === "/api/shelves") return new Response(JSON.stringify(shelves));
      return new Response("[]");
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByText("Favorites");
    await user.type(
      screen.getByPlaceholderText(/new shelf name/i),
      "Favorites",
    );
    await user.click(screen.getByRole("button", { name: /create shelf/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /already in use/i,
    );
  });
});
