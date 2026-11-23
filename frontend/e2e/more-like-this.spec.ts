import AxeBuilder from "@axe-core/playwright";

import { expect, isHome, test } from "./console";
import {
  ATTRIBUTION,
  film,
  movieType,
  stubSuggestions,
} from "./suggest-fixture";

/**
 * *More like this* (Sprint 134): the button on a film's page opens a sheet that
 * asks once, fills in as the round's job reports on the event stream, and keeps
 * each answer across a reload; without a configured source it says how to set one
 * up and asks nothing. Home shows the newest found picks with TMDB's line. Axe
 * passes with the sheet open, and it fits a 390px phone.
 */

test("the sheet fills in from the event stream and keeps its answers", async ({
  page,
}) => {
  const state = await stubSuggestions(page);
  await page.goto("/books/7");
  await page.getByRole("button", { name: "More like Seven Samurai" }).click();
  const sheet = page.getByRole("dialog", { name: "More like Seven Samurai" });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByText(ATTRIBUTION)).toBeVisible();

  // The picks arrive first, then the first three are found: both from the stream.
  const list = sheet.getByRole("list", { name: "Suggestions" });
  await expect(list.getByRole("listitem")).toHaveCount(5);
  await expect(
    sheet.getByText("5 picked by TMDB in one request · 3 found so far"),
  ).toBeVisible();
  expect(
    state.requests.filter((r) => r === "POST /api/entries/7/more-like-this"),
  ).toHaveLength(1);

  // Opening a pending one looks it up; the stream says when it is found.
  await list.getByRole("button", { name: "Look up Rashomon (1950)" }).click();
  await expect(
    list.getByRole("button", { name: "Want Rashomon (1950)" }),
  ).toBeVisible();
  await expect(
    sheet.getByText("5 picked by TMDB in one request · 4 found so far"),
  ).toBeVisible();

  await list.getByRole("button", { name: "Want Yojimbo (1961)" }).click();
  await expect(
    list.getByRole("link", { name: "On your list" }),
  ).toHaveAttribute("href", "/books/90");
  await list
    .getByRole("button", { name: "Not for me: Kagemusha (1980)" })
    .click();
  await expect(list.getByText("Not for you")).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "More like Seven Samurai" }).click();
  const again = page.getByRole("dialog", { name: "More like Seven Samurai" });
  await expect(again.getByRole("link", { name: "On your list" })).toBeVisible();
  await expect(again.getByText("Not for you")).toBeVisible();
  await expect(again.getByRole("button", { name: "Refresh" })).toBeEnabled();
});

test("without a configured source the button explains and asks nothing", async ({
  page,
}) => {
  const state = await stubSuggestions(page, { configured: false });
  await page.goto("/books/7");
  await page.getByRole("button", { name: "More like Seven Samurai" }).click();
  const sheet = page.getByRole("dialog", { name: "More like Seven Samurai" });
  await expect(sheet.getByText(/Set TMDB_READ_TOKEN/)).toBeVisible();
  await expect(sheet.getByRole("button", { name: "Refresh" })).toHaveCount(0);
  expect(state.requests.some((r) => r.includes("more-like-this"))).toBe(false);
});

test("Home shows the newest found picks with TMDB's line", async ({ page }) => {
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [movieType(true)] }),
  );
  await page.route(isHome, async (route) => {
    await route.fulfill({
      json: {
        greeting: {
          today: "2026-11-23",
          active: null,
          entries: 1,
          pile: 0,
          goals: [],
        },
        now: [film],
        next: [],
        year: null,
        domains: [],
        lately: [],
        tidy: null,
        question: null,
        shelves: [],
        lent: { total: 0, loans: [] },
        suggested: ["Yojimbo", "Kagemusha", "After the Rain"].map(
          (title, index) => ({
            id: 100 + index,
            round_id: 7,
            item_type: "movie",
            source: "fake",
            title,
            year: 1961 + index,
            creator: null,
            external_ids: {},
            reason: { signal: "fake", text: "TMDB: often watched together" },
            source_score: null,
            display: {},
            enrichment: "enriched",
            item_id: 50 + index,
            entry_id: null,
            cover_url: null,
            seed: { entry_id: 7, title: "Seven Samurai" },
            answer: null,
            answered_at: null,
            created_at: "2026-11-23T10:00:00Z",
          }),
        ),
      },
    });
  });
  await page.goto("/");
  const module = page.getByRole("region", { name: "More like this" });
  await expect(module.getByRole("listitem")).toHaveCount(3);
  await expect(module.getByText(ATTRIBUTION)).toBeVisible();
  await expect(module.getByText("Like Seven Samurai").first()).toBeVisible();
  // On now offers it too, for a film.
  await expect(
    page
      .getByRole("region", { name: "On now" })
      .getByRole("button", { name: "More like Seven Samurai" }),
  ).toBeVisible();
});

for (const width of [390, 1440]) {
  test(`the open sheet fits and has no serious axe violations at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await stubSuggestions(page);
    await page.goto("/books/7");
    await page.getByRole("button", { name: "More like Seven Samurai" }).click();
    const sheet = page.getByRole("dialog", { name: "More like Seven Samurai" });
    await expect(
      sheet.getByText("5 picked by TMDB in one request · 3 found so far"),
    ).toBeVisible();
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBe(0);
    const box = await sheet.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const serious = results.violations.filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical",
    );
    expect(
      serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`),
    ).toEqual([]);
  });
}
