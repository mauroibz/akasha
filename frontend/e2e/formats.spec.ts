import { type Page } from "@playwright/test";
import { expect, test } from "./console";

import { albumItemType, bookItemType, stubItemTypes } from "./seed";

/**
 * DEC-059 in a browser: status and format are independent axes.
 *
 * The two readings the owner asked for are "I can sort by owned and see where I
 * own it" and "mark something wishlist → vinyl, so I can schedule my next
 * purchase". Both are asserted here, because a unit test can prove the request
 * body and still leave the answer one click away on another screen.
 */

const album = (overrides: Record<string, unknown> = {}) => ({
  id: 9,
  item_id: 9,
  status: "owned",
  score: null,
  notes: null,
  date_added: "2026-08-15T00:00:00Z",
  date_started: null,
  date_finished: null,
  reread_count: 0,
  score_provisional: false,
  suggested_status: null,
  item: {
    id: 9,
    type: "album",
    title: "Discovery",
    subtitle: null,
    year: 2001,
    creator: "Daft Punk",
    creator_sort: "Daft Punk",
    cover_url: null,
    cover_path: null,
    metadata: { creators: ["Daft Punk"], label: "Virgin" },
    identifiers: {},
    sources: [],
  },
  shelves: [],
  formats: ["vinyl"],
  ...overrides,
});

async function library(page: Page, entries: unknown[], counts = {}) {
  await stubItemTypes(page, [bookItemType, albumItemType]);
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: {
          status_counts: { owned: 1 },
          status_counts_by_type: { album: { owned: 1 }, book: { read: 4 } },
          format_counts: { vinyl: 1, ...counts },
        },
      },
    }),
  );
}

test("the format of a copy is readable from the library row", async ({
  page,
}) => {
  await library(page, [album()]);
  await page.goto("/");

  const row = page.getByRole("article").filter({ hasText: "Discovery" });
  await expect(row.locator("[data-card-formats]")).toContainText("Vinyl");
});

test("the status filter offers the chosen domain's vocabulary, and only that domain's", async ({
  page,
}) => {
  // Sprint 029 removed "All", so exactly one domain is named at a time. The rule
  // this replaces -- a row of chips per domain, each under its own heading --
  // existed for the filter that is gone, and the chips themselves folded into one
  // control in 029's second pass. What still has to hold is that no domain's
  // vocabulary leaks into another's list.
  await library(page, [album()]);
  await page.goto("/");

  const status = page.getByRole("combobox", { name: "Filter by status" });
  await status.click();
  await expect(page.getByRole("option", { name: /^Read \d/ })).toBeVisible();
  await expect(page.getByRole("option", { name: /^Owned/ })).toHaveCount(0);
  await page.keyboard.press("Escape");

  await page.getByRole("radio", { name: "Album" }).click();
  await status.click();
  await expect(page.getByRole("option", { name: /^Owned/ })).toBeVisible();
  await expect(page.getByRole("option", { name: /^Read \d/ })).toHaveCount(0);
});

test("filtering to owned asks the server for that status", async ({ page }) => {
  await library(page, [album()]);
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/entries")) requests.push(request.url());
  });
  await page.goto("/");

  await page.getByRole("radio", { name: "Album" }).click();
  await page.getByRole("combobox", { name: "Filter by status" }).click();
  await page.getByRole("option", { name: /^Owned/ }).click();

  await expect
    .poll(() => requests.some((url) => url.includes("status=owned")))
    .toBe(true);
});

test("a wishlist record can be marked vinyl without either implying the other", async ({
  page,
}) => {
  const wishlisted = album({ status: "wishlist", formats: [] });
  await library(page, [wishlisted]);
  await page.route("**/api/entries/9", async (route) => {
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      // The whole point of DEC-059: the patch carries the format and leaves the
      // status alone, so "the pressing I mean to buy" is expressible.
      expect(body.formats).toEqual(["vinyl"]);
      expect(body.status).toBe("wishlist");
      await route.fulfill({ json: { ...wishlisted, formats: ["vinyl"] } });
      return;
    }
    await route.fulfill({ json: wishlisted });
  });
  await page.goto("/books/9");

  await page.getByRole("button", { name: "Edit opinion" }).click();
  // A record's opinion form offers no reread count and no dates (DEC-057).
  await expect(page.getByLabel("Reread count")).toHaveCount(0);
  await expect(page.getByLabel("Started")).toHaveCount(0);
  // One control, shared with the add screen: a closed vocabulary you pick from,
  // and deliberately never the shelf control, which is the one you type into.
  await page.getByRole("combobox", { name: "Format" }).click();
  await page.getByRole("option", { name: "Vinyl" }).click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Save opinion" }).click();

  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("an album's tracklist reads in order with its lengths", async ({
  page,
}) => {
  const withTracks = album({
    item: {
      ...album().item,
      metadata: {
        creators: ["Daft Punk"],
        tracklist: [
          { position: 1, title: "One More Time", length_ms: 320306 },
          { position: 2, title: "Aerodynamic", length_ms: 212506 },
        ],
      },
    },
  });
  await library(page, [withTracks]);
  await page.route("**/api/entries/9", (route) =>
    route.fulfill({ json: withTracks }),
  );
  await page.goto("/books/9");

  const tracks = page.locator("[data-rows='tracklist'] li");
  await expect(tracks).toHaveCount(2);
  await expect(tracks.first()).toContainText("One More Time");
  await expect(tracks.first()).toContainText("5:20");
  await expect(tracks.nth(1)).toContainText("3:32");
});
