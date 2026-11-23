import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./HomePage";
import { fallbackLayout } from "./layout";
import { emptyHome, fullHome, renderWithRouter, types } from "./testHome";
import type { ModuleLayout } from "@/api/home";

afterEach(() => vi.restoreAllMocks());

function serve(home: object, layout: ModuleLayout[] = fallbackLayout) {
  const puts: ModuleLayout[][] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/home/layout")) {
        if (init?.method === "PUT") {
          const { modules } = JSON.parse(String(init.body)) as {
            modules: ModuleLayout[];
          };
          puts.push(modules);
          return new Response(
            JSON.stringify({ modules, defaults: fallbackLayout }),
          );
        }
        return new Response(
          JSON.stringify({ modules: layout, defaults: fallbackLayout }),
        );
      }
      if (url.includes("/api/home")) return new Response(JSON.stringify(home));
      if (url.includes("/api/item-types"))
        return new Response(JSON.stringify(types));
      return new Response("[]");
    }),
  );
  return puts;
}

const regionNames = () =>
  screen
    .getAllByRole("region")
    .map((region) => region.getAttribute("aria-labelledby"))
    .map((id) => document.getElementById(id ?? "")?.textContent);

describe("HomePage", () => {
  it("lays out every module from the one payload", async () => {
    serve(fullHome());
    renderWithRouter(<HomePage />);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      /Day 32 of/,
    );
    for (const name of [
      "On now",
      "Up next",
      "2026",
      "Lately",
      "Your libraries",
      "Tidy up",
      "One question",
      "Shelves",
      "Lent out",
    ]) {
      expect(screen.getByRole("region", { name })).toBeVisible();
    }
  });

  it("asks for Home in the person's own zone", async () => {
    serve(fullHome());
    renderWithRouter(<HomePage />);
    await screen.findByRole("heading", { level: 1 });
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const urls = vi.mocked(fetch).mock.calls.map(([input]) => String(input));
    expect(urls).toContain(`/api/home?tz=${encodeURIComponent(zone)}`);
  });

  it("follows the stored order and leaves out hidden and empty modules", async () => {
    const home = fullHome();
    home.lent = { total: 0, loans: [] };
    const layout = [
      { module: "lately", size: "S", hidden: false },
      { module: "now", size: "M", hidden: false },
      { module: "year", size: "L", hidden: true },
    ] as ModuleLayout[];
    serve(home, [
      ...layout,
      ...fallbackLayout.filter(
        (row) => !["lately", "now", "year"].includes(row.module),
      ),
    ]);
    renderWithRouter(<HomePage />);
    await screen.findByRole("region", { name: "Lately" });
    await waitFor(() =>
      expect(regionNames()).toEqual([
        "Lately",
        "On now",
        "Up next",
        "Your libraries",
        "Tidy up",
        "One question",
        "Shelves",
      ]),
    );
  });

  it("draws a library's year and a placed shelf where the layout puts them (DEC-192)", async () => {
    const home = {
      ...fullHome(),
      library_years: [
        {
          item_type: "movie",
          year: 2026,
          total: 1,
          goal: null,
          covers: [
            {
              entry_id: 70,
              item_id: 70,
              item_type: "movie",
              title: "Paris, Texas",
              cover_url: null,
              score: 9,
            },
          ],
        },
      ],
      shelf_modules: [
        {
          id: 3,
          name: "Favorites",
          slug: "favorites",
          entry_count: 1,
          covers: [
            {
              entry_id: 71,
              item_id: 71,
              item_type: "book",
              title: "Rayuela",
              cover_url: null,
              score: 10,
            },
          ],
        },
      ],
    };
    serve(home, [
      { module: "shelf:3", size: "M", hidden: false, label: "Favorites" },
      {
        module: "year:movie",
        size: "M",
        hidden: false,
        label: "Movies this year",
      },
      // Shown, but the payload has nothing for it: not drawn.
      {
        module: "year:anime",
        size: "M",
        hidden: false,
        label: "Anime this year",
      },
      { module: "shelf:4", size: "M", hidden: true, label: "Hidden" },
      ...fallbackLayout,
    ] as ModuleLayout[]);
    renderWithRouter(<HomePage />);
    const shelf = await screen.findByRole("region", { name: "Favorites" });
    expect(
      within(shelf).getByRole("link", { name: "Rayuela" }),
    ).toHaveAttribute("href", "/books/71");
    expect(
      within(shelf).getByRole("link", { name: "1 on the shelf →" }),
    ).toHaveAttribute("href", "/shelves/favorites");
    const year = screen.getByRole("region", { name: "Your 2026 movies" });
    expect(
      within(year).getByRole("link", { name: "Paris, Texas" }),
    ).toBeVisible();
    expect(regionNames().slice(0, 2)).toEqual([
      "Favorites",
      "Your 2026 movies",
    ]);
    expect(regionNames()).not.toContain("Your 2026 anime");
  });

  it("stores a change made in Edit home", async () => {
    const puts = serve(fullHome());
    renderWithRouter(<HomePage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit home" }));
    const dialog = screen.getByRole("dialog", { name: "Edit home" });
    await user.click(
      within(dialog).getByRole("switch", { name: "Show Shelves" }),
    );
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].find((row) => row.module === "shelves")?.hidden).toBe(true);
    await user.click(within(dialog).getByRole("button", { name: "Done" }));
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Shelves" })).toBeNull(),
    );
  });

  it("welcomes an empty library instead of drawing empty modules", async () => {
    serve(emptyHome());
    renderWithRouter(<HomePage />);
    expect(
      await screen.findByRole("heading", { name: "Your desk is ready" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Add something" })).toHaveAttribute(
      "href",
      "/add",
    );
    expect(
      screen.getByRole("link", { name: "Import a library" }),
    ).toHaveAttribute("href", "/import");
    expect(screen.queryByRole("region", { name: "On now" })).toBeNull();
  });

  it("says so when Home cannot be loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 500 })),
    );
    renderWithRouter(<HomePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Home could not be loaded/,
    );
  });
});
