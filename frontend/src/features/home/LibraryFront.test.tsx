import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ModuleLayout } from "@/api/home";

import { fallbackLayout } from "./layout";
import { LibraryFront } from "./LibraryFront";
import { emptyHome, fullHome, renderWithRouter, types } from "./testHome";

afterEach(() => vi.restoreAllMocks());

const everything: ModuleLayout[] = fallbackLayout.map((row) => ({
  ...row,
  hidden: false,
}));

function serve(home: object | null, layout: ModuleLayout[] = everything) {
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
      if (url.includes("/api/home"))
        return home
          ? new Response(JSON.stringify(home))
          : new Response("{}", { status: 500 });
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
    .map(
      (region) =>
        region.getAttribute("aria-label") ??
        document.getElementById(region.getAttribute("aria-labelledby") ?? "")
          ?.textContent,
    );

describe("LibraryFront (Sprint 141, DEC-193)", () => {
  it("opens with the greeting, then what is under way, then lately, then the showcases", async () => {
    serve(fullHome());
    renderWithRouter(<LibraryFront />);
    expect(
      await screen.findByRole("heading", { level: 2, name: /Day 32 of/ }),
    ).toBeVisible();
    await waitFor(() =>
      expect(regionNames()).toEqual([
        "Your library today",
        "On now",
        "Lately",
        "Up next",
        "One question",
      ]),
    );
  });

  it("asks in the person's own zone", async () => {
    serve(fullHome());
    renderWithRouter(<LibraryFront />);
    await screen.findByRole("region", { name: "Lately" });
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const urls = vi.mocked(fetch).mock.calls.map(([input]) => String(input));
    expect(urls).toContain(`/api/home?tz=${encodeURIComponent(zone)}`);
  });

  it("shows only what the person placed, in their order; the bands are not theirs to hide", async () => {
    serve(fullHome(), [
      { module: "question", size: "S", hidden: false },
      { module: "next", size: "L", hidden: true },
      { module: "suggested", size: "M", hidden: true },
    ]);
    renderWithRouter(<LibraryFront />);
    await screen.findByRole("region", { name: "One question" });
    expect(regionNames()).toEqual([
      "Your library today",
      "On now",
      "Lately",
      "One question",
    ]);
  });

  it("draws a library's year and a placed shelf where the layout puts them (DEC-192)", async () => {
    const home = {
      ...fullHome(),
      library_years: [
        {
          item_type: "book",
          year: 2026,
          total: 1,
          goal: null,
          covers: [
            {
              entry_id: 20,
              item_id: 120,
              item_type: "book",
              title: "Slaughterhouse-Five",
              cover_url: null,
              score: 8,
            },
          ],
        },
      ],
      shelf_modules: [
        {
          id: 7,
          name: "Horror",
          slug: "horror",
          entry_count: 1,
          covers: [
            {
              entry_id: 43,
              item_id: 143,
              item_type: "book",
              title: "Pet Sematary",
              cover_url: null,
              score: 9,
            },
          ],
        },
      ],
    };
    serve(home, [
      { module: "shelf:7", size: "M", hidden: false },
      { module: "year:book", size: "M", hidden: false },
      ...fallbackLayout,
    ]);
    renderWithRouter(<LibraryFront />);
    const shelf = await screen.findByRole("region", { name: "Horror" });
    expect(
      within(shelf).getByRole("link", { name: /Pet Sematary/ }),
    ).toBeVisible();
    const names = regionNames();
    expect(names.indexOf("Horror")).toBeLessThan(
      names.findIndex((name) => /2026/.test(name ?? "")),
    );
  });

  it("stores a change made while arranging", async () => {
    const puts = serve(fullHome());
    renderWithRouter(<LibraryFront />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Edit home" }),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialog).getAllByRole("switch", { checked: true })[0],
    );
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].filter((row) => row.hidden)).toHaveLength(1);
  });

  it("draws nothing for an empty library, which has its own first screen", async () => {
    serve(emptyHome());
    const { container } = renderWithRouter(<LibraryFront />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container.querySelector("section")).toBeNull();
  });

  it("draws nothing when it cannot be read: the Library below does not depend on it", async () => {
    serve(null);
    const { container } = renderWithRouter(<LibraryFront />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container.querySelector("section")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
