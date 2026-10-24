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
  plural_label: "Books",
};

const albumType = {
  ...bookType,
  id: "album",
  label: "Album",
  plural_label: "Albums",
};

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
    finished_count: 3,
    mean_score: 8.6,
    preview: [
      {
        entry_id: 11,
        title: "Rayuela",
        year: 1963,
        score: 10,
        cover_url: "/api/items/11/cover?v=1",
      },
      {
        entry_id: 12,
        title: "Ficciones",
        year: 1944,
        score: 9,
        cover_url: null,
      },
    ],
  },
  {
    id: 2,
    name: "Sci-fi",
    slug: "sci-fi",
    entry_count: 3,
    covers: [],
    members_by_type: { book: 3 },
    finished_count: 0,
    mean_score: null,
    preview: [],
  },
];

function stubApi(
  rows: unknown[] = shelves,
  types: unknown[] = [bookType],
  loans: unknown[] = [],
) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.startsWith("/api/loans"))
      return new Response(JSON.stringify(loans));
    if (url === "/api/item-types") return new Response(JSON.stringify(types));
    if (url === "/api/shelves") return new Response(JSON.stringify(rows));
    if (init?.method === "POST" && url === "/api/shelves")
      return new Response(JSON.stringify({ id: 3, name: "New", slug: "new" }));
    return new Response("[]");
  });
}

const loan = (id: number, person: string, title: string, lentOn: string) => ({
  id,
  entry_id: id + 100,
  person,
  lent_on: lentOn,
  returned_on: null,
  note: null,
  entry: {
    id: id + 100,
    status: "read",
    score: 9,
    item: { id, type: "book", title, year: 1963, cover_url: null },
  },
});

describe("ShelvesPage: what is lent out (Sprint 122)", () => {
  it("stands open loans as the first ledge, with who has the longest out", async () => {
    stubApi(
      shelves,
      [bookType],
      [
        loan(1, "Sofi", "Rayuela", "2026-04-02"),
        loan(2, "Juan", "Ficciones", "2026-09-01"),
      ],
    );
    renderPage();
    const ledge = (await waitFor(() => {
      const row = document.querySelector('[data-shelf-row="lent"]');
      expect(row).not.toBeNull();
      return row;
    })) as HTMLElement;
    expect(
      within(ledge).getByRole("link", { name: "Lent out" }),
    ).toHaveAttribute("href", "/lent");
    expect(ledge).toHaveTextContent(/2 things · Rayuela has been with Sofi/);
    expect(
      within(ledge).getByRole("link", { name: "Rayuela, 1963, scored 9" }),
    ).toHaveAttribute("href", "/books/101");
    // First, above every shelf of the owner's.
    const rows = [...document.querySelectorAll("[data-shelf-row]")];
    expect(rows[0]).toBe(ledge);
  });

  it("draws nothing when nothing is out", async () => {
    stubApi();
    renderPage();
    await screen.findByRole("link", { name: "Favorites" });
    expect(document.querySelector('[data-shelf-row="lent"]')).toBeNull();
  });
});

describe("ShelvesPage", () => {
  it("reads the room back in a sentence, and each shelf in a line", async () => {
    stubApi();
    renderPage();
    expect(
      await screen.findByText(
        (_, node) =>
          node?.tagName === "P" &&
          node.textContent ===
            "Two shelves, 8 things on them. Your best-loved is Favorites.",
      ),
    ).toBeInTheDocument();
    const favorites = document.querySelector(
      '[data-shelf-row="favorites"]',
    ) as HTMLElement;
    expect(favorites).toHaveTextContent(
      "5 books · 3 finished · you rate them 8.6",
    );
    expect(within(favorites).getByText("Books")).toBeVisible();
  });

  it("stands the preview on the ledge as covers that open, each a link", async () => {
    stubApi();
    renderPage();
    const cover = await screen.findByRole("link", {
      name: "Rayuela, 1963, scored 10",
    });
    expect(cover).toHaveAttribute("href", "/books/11");
    expect(cover).toHaveAttribute("data-opening-cover");
    // No art: a typeset cover carries the title instead of an empty box.
    const typeset = screen.getByRole("link", {
      name: "Ficciones, 1944, scored 9",
    });
    expect(within(typeset).getAllByText("Ficciones")).toHaveLength(2);
    expect(screen.getByRole("link", { name: /See all 5/ })).toHaveAttribute(
      "href",
      "/shelves/favorites",
    );
  });

  it("draws an empty shelf as a dashed place and says so", async () => {
    stubApi([
      {
        id: 9,
        name: "Walkthrough",
        slug: "walkthrough",
        entry_count: 0,
        covers: [],
        members_by_type: {},
        preview: [],
        finished_count: 0,
        mean_score: null,
      },
    ]);
    renderPage();
    const row = await screen.findByText("Walkthrough");
    const shelf = row.closest("[data-shelf-row]") as HTMLElement;
    expect(shelf).toHaveTextContent("Empty");
    expect(shelf).toHaveTextContent("Nothing here yet.");
  });

  it("a shelf's name links into its own page", async () => {
    stubApi();
    renderPage();
    const link = await screen.findByRole("link", { name: "Favorites" });
    expect(link).toHaveAttribute("href", "/shelves/favorites");
  });

  it("creates a shelf from a button, not a standing field", async () => {
    let created = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify([bookType]));
      if (init?.method === "POST" && url === "/api/shelves") {
        created = true;
        return new Response(
          JSON.stringify({ id: 3, name: "New", slug: "new", entry_count: 0 }),
          {
            status: 201,
          },
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
    await screen.findByRole("link", { name: "Favorites" });
    expect(
      screen.queryByRole("textbox", { name: "New shelf name" }),
    ).toBeNull();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "+ New shelf" }));
    await user.type(
      screen.getByRole("textbox", { name: "New shelf name" }),
      "New",
    );
    await user.click(screen.getByRole("button", { name: "Create shelf" }));
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "New" })).toBeVisible(),
    );
  });

  it("the domain filter narrows the room", async () => {
    stubApi(
      [
        {
          id: 1,
          name: "Books only",
          slug: "books-only",
          entry_count: 5,
          covers: [],
          members_by_type: { book: 5 },
          preview: [],
        },
        {
          id: 2,
          name: "Mixed",
          slug: "mixed",
          entry_count: 8,
          covers: [],
          members_by_type: { book: 5, album: 3 },
          preview: [],
        },
      ],
      [bookType, albumType],
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Books only");
    const mixed = document.querySelector(
      '[data-shelf-row="mixed"]',
    ) as HTMLElement;
    expect(mixed).toHaveTextContent("Books · Albums");
    expect(mixed).toHaveTextContent("8 things");

    await user.click(screen.getByRole("radio", { name: "Albums" }));
    expect(screen.queryByText("Books only")).not.toBeInTheDocument();
    expect(screen.getByText("Mixed")).toBeVisible();

    await user.click(screen.getByRole("radio", { name: "All" }));
    expect(screen.getByText("Books only")).toBeVisible();
  });

  it("sorts by size (default), by name, and by recently changed", async () => {
    stubApi([
      {
        id: 1,
        name: "Zeta",
        slug: "zeta",
        entry_count: 1,
        covers: [],
        members_by_type: { book: 1 },
        preview: [],
        updated_at: "2026-09-05T00:00:00Z",
      },
      {
        id: 2,
        name: "Alpha",
        slug: "alpha",
        entry_count: 9,
        covers: [],
        members_by_type: { book: 9 },
        preview: [],
        updated_at: "2026-09-01T00:00:00Z",
      },
    ]);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Zeta");
    const names = () =>
      [...document.querySelectorAll("[data-shelf-row]")].map((node) =>
        node.getAttribute("data-shelf-row"),
      );
    expect(names()).toEqual(["alpha", "zeta"]);
    await user.click(screen.getByRole("button", { name: "Recent" }));
    expect(names()).toEqual(["zeta", "alpha"]);
    await user.click(screen.getByRole("button", { name: "A–Z" }));
    expect(names()).toEqual(["alpha", "zeta"]);
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
    await screen.findByRole("link", { name: "Favorites" });
    await user.click(screen.getByRole("button", { name: "+ New shelf" }));
    await user.type(
      screen.getByRole("textbox", { name: "New shelf name" }),
      "Favorites",
    );
    await user.click(screen.getByRole("button", { name: "Create shelf" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Shelf name is already in use",
    );
  });
});
