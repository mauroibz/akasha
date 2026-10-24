import type { Page } from "@playwright/test";

import { bookItemType, movieItemType } from "./seed";

/** Suggested shelves as Sprint 119's API answers them; the shelf list is stateful. */
export async function stubSuggestions(page: Page, posts: unknown[] = []) {
  const member = (id: number, title: string) => ({
    entry_id: id,
    title,
    year: 1970,
    score: 9,
    cover_url: null,
  });
  let offered = [
    {
      key: "creator:ursula k le guin",
      kind: "creator",
      name: "Ursula K. Le Guin",
      reason: "3 by Ursula K. Le Guin",
      members: [
        member(1, "The Dispossessed"),
        member(2, "The Left Hand of Darkness"),
        member(3, "The Lathe of Heaven"),
      ],
    },
    {
      key: "work:dune",
      kind: "work",
      name: "Dune",
      reason: "Dune in 2 libraries",
      members: [member(4, "Dune"), member(5, "Dune: Part One")],
    },
  ];
  const shelves: Array<Record<string, unknown>> = [];
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [bookItemType, movieItemType] }),
  );
  await page.route("**/api/shelves", (route) =>
    route.fulfill({ json: shelves }),
  );
  await page.route("**/api/shelves/suggestions", (route) =>
    route.fulfill({ json: offered }),
  );
  await page.route("**/api/shelves/suggestions/*", (route) => {
    const body = route.request().postDataJSON() as { key: string };
    posts.push({ url: new URL(route.request().url()).pathname, body });
    const chosen = offered.find((row) => row.key === body.key);
    offered = offered.filter((row) => row.key !== body.key);
    if (route.request().url().endsWith("/accept") && chosen) {
      const shelf = {
        id: shelves.length + 1,
        name: chosen.name,
        slug: "ursula-k-le-guin",
        updated_at: "2026-10-23T00:00:00Z",
        entry_count: chosen.members.length,
        covers: [],
        members_by_type: { book: chosen.members.length },
        preview: chosen.members,
        finished_count: 0,
        mean_score: 9,
      };
      shelves.push(shelf);
      return route.fulfill({ status: 201, json: shelf });
    }
    return route.fulfill({ status: 204 });
  });
}
