import type { Page, Request } from "@playwright/test";

import { expect, test } from "./console";
import { pixelCover, stubImporters, stubItemTypes } from "./seed";

/**
 * The inbox one card at a time (Sprint 106, DEC-170). The owner's screenshot
 * was the list at phone width with every title cut to three letters; these
 * hold the deck to its promise there: the whole title and every control on one
 * screen, and a swipe that files or passes.
 */

const titles = [
  "A Swim in a Pond in the Rain: In Which Four Russians Give a Master Class on Writing, Reading, and Life",
  "A Story of Love and Hope in the Time of the Long Night",
  "A Clockwork Orange",
  "A Game of Thrones",
];

function makeEntries() {
  return titles.map((title, index) => ({
    id: index + 1,
    item_id: index + 1,
    status: "unsorted",
    score: index === 1 ? 7 : null,
    notes: null,
    date_added: "2026-10-01",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    progress: null,
    score_provisional: index === 1,
    suggested_status: index === 0 ? "read" : null,
    item: {
      id: index + 1,
      type: "book",
      title,
      subtitle: null,
      year: 1960 + index,
      creator: "George Saunders",
      cover_url: index % 2 === 0 ? pixelCover : null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    shelves: [],
    formats: [],
  }));
}

async function stubDeck(page: Page) {
  const entries = makeEntries();
  const patches: Array<{ url: string; body: unknown }> = [];
  await stubImporters(page);
  await stubItemTypes(page);
  await page.route("**/api/shelves", (route) =>
    route.fulfill({
      json: [
        { id: 1, name: "Favorites", slug: "favorites", entry_count: 1 },
        { id: 2, name: "Russians", slug: "russians", entry_count: 0 },
      ],
    }),
  );
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: {
          status_counts: { unsorted: entries.length },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route(/\/api\/entries\/\d+$/, (route) => {
    const request: Request = route.request();
    const body = request.postDataJSON() as Record<string, unknown>;
    patches.push({ url: new URL(request.url()).pathname, body });
    const id = Number(request.url().split("/").at(-1));
    return route.fulfill({
      json: { ...entries.find((row) => row.id === id), ...body },
    });
  });
  return patches;
}

/** Everything a decision needs, inside the viewport, with nothing scrolled. */
async function expectEverythingOnScreen(page: Page) {
  const viewport = page.viewportSize()!;
  const inside = async (name: string, locator: ReturnType<Page["locator"]>) => {
    const box = await locator.boundingBox();
    expect(box, name).not.toBeNull();
    expect(box!.y, `${name} top`).toBeGreaterThanOrEqual(0);
    expect(box!.y + box!.height, `${name} bottom`).toBeLessThanOrEqual(
      viewport.height,
    );
    expect(box!.x + box!.width, `${name} right`).toBeLessThanOrEqual(
      viewport.width,
    );
  };
  await inside("card", page.locator("[data-deck-card]"));
  await inside("title", page.getByTestId("deck-title"));
  await inside("statuses", page.getByRole("button", { name: "Dropped" }));
  await inside("score", page.getByRole("button", { name: "Score 10" }));
  await inside("later", page.getByRole("button", { name: /later/i }));
  await inside("file", page.getByRole("button", { name: /^file as/i }));
  // The whole title is set, not cut: its box holds all of it.
  const title = page.getByTestId("deck-title");
  expect(
    await title.evaluate((node) => node.scrollHeight <= node.clientHeight + 1),
  ).toBe(true);
  // Nothing scrolls: the layer holds it all, once a departing card has gone.
  await expect(page.locator("[data-departing]")).toHaveCount(0);
  const layerScrolls = await page.evaluate(() => {
    const layer = document.querySelector('[role="dialog"]')!;
    return layer.scrollHeight > layer.clientHeight + 1;
  });
  expect(layerScrolls).toBe(false);
}

test("the inbox opens the deck with its own filter", async ({ page }) => {
  await stubDeck(page);
  await page.goto("/inbox?q=saunders");
  await page.getByRole("link", { name: /one at a time/i }).click();
  await expect(page).toHaveURL(/\/inbox\/deck\?q=saunders$/);
  await expect(page.getByTestId("deck-title")).toHaveText(titles[0]);
  await page.getByRole("button", { name: /back to the inbox/i }).click();
  await expect(page).toHaveURL(/\/inbox\?q=saunders$/);
});

for (const size of [
  { name: "a phone", width: 390, height: 664 },
  { name: "a desktop", width: 1440, height: 900 },
]) {
  test(`on ${size.name} the cover, the whole title and every control fit`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: size.width, height: size.height });
    await stubDeck(page);
    await page.goto("/inbox/deck");
    await expect(page.getByTestId("deck-title")).toHaveText(titles[0]);
    await expectEverythingOnScreen(page);
    // The provisional card says so, and still fits.
    await page.getByRole("button", { name: /later/i }).click();
    await expect(page.getByTestId("deck-title")).toHaveText(titles[1]);
    await expect(page.getByText(/score from the import/i)).toBeVisible();
    await expectEverythingOnScreen(page);
  });
}

async function swipe(page: Page, distance: number) {
  const box = (await page.locator("[data-deck-card]").boundingBox())!;
  const y = box.y + box.height / 3;
  const x = box.x + box.width / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  for (let step = 1; step <= 8; step++)
    await page.mouse.move(x + (distance * step) / 8, y);
  await page.mouse.up();
}

test("a swipe right files the card and a swipe left passes it", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 664 });
  const patches = await stubDeck(page);
  await page.goto("/inbox/deck");
  await expect(page.getByTestId("deck-title")).toHaveText(titles[0]);

  await swipe(page, 220);
  await expect(page.getByTestId("deck-title")).toHaveText(titles[1]);
  await expect.poll(() => patches.length).toBe(1);
  expect(patches[0]).toEqual({
    url: "/api/entries/1",
    body: { status: "read" },
  });

  await swipe(page, -220);
  await expect(page.getByTestId("deck-title")).toHaveText(titles[2]);
  // A short drag springs back and decides nothing.
  await swipe(page, 40);
  await expect(page.getByTestId("deck-title")).toHaveText(titles[2]);
  expect(patches).toHaveLength(1);
});

test("the end of the deck offers the passed cards again", async ({ page }) => {
  const patches = await stubDeck(page);
  await page.goto("/inbox/deck");
  await expect(page.getByTestId("deck-title")).toHaveText(titles[0]);
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("t");
  await page.keyboard.press("9");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");

  await expect(
    page.getByRole("heading", { name: /that’s the deck/i }),
  ).toBeVisible();
  await expect(page.getByText("3 filed · 1 left for later.")).toBeVisible();
  await page
    .getByRole("button", { name: "Go through the 1 you passed" })
    .click();
  await expect(page.getByTestId("deck-title")).toHaveText(titles[0]);
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("heading", { name: "Inbox clear" }),
  ).toBeVisible();

  await expect.poll(() => patches.length).toBe(4);
  expect(patches[0].body).toEqual({ status: "to_read", score: 9 });
});
