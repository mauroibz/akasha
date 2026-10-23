import type { Page } from "@playwright/test";

import { expect, test } from "./console";
import { rankEntry } from "./rank-fixture";
import { bookItemType } from "./seed";

/** The tier board (Sprint 117, DEC-176): moves proposed, applied on confirmation. */

async function stubTiers(page: Page, writes: unknown[] = []) {
  const entries = [
    { ...rankEntry(1, "Piranesi", null), score: 9 },
    ...Array.from({ length: 9 }, (_, index) => ({
      ...rankEntry(index + 2, `Eight ${index + 1}`, null),
      score: 8,
    })),
    { ...rankEntry(20, "Ficciones", null), score: 6 },
  ];
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [bookItemType] }),
  );
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: entries,
        next_cursor: null,
        total: entries.length,
        facets: {
          status_counts: {},
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route(/\/api\/entries\/(rank|\d+)$/, (route) => {
    writes.push({
      method: route.request().method(),
      url: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    });
    return route.fulfill({
      json: route.request().method() === "PUT" ? [] : entries[0],
    });
  });
}

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("a full row scrolls inside itself and the page does not", async ({
    page,
  }) => {
    await stubTiers(page);
    await page.goto("/tiers/book");
    const eight = page.getByRole("group", { name: "8", exact: true });
    await expect(eight.getByRole("button", { name: "Eight 9" })).toBeAttached();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    // A proposal's bar sits above the bottom navigation, where a thumb reaches it.
    await page.getByRole("button", { name: "Ficciones" }).click();
    await page
      .getByRole("group", { name: "7", exact: true })
      .getByRole("button", { name: "Place it here, as 7" })
      .click();
    const apply = page.getByRole("button", { name: "Apply 1 change" });
    await expect(apply).toBeVisible();
    expect(
      await apply.evaluate((node) => {
        const rect = node.getBoundingClientRect();
        const hit = document.elementFromPoint(
          rect.x + rect.width / 2,
          rect.y + rect.height / 2,
        );
        return hit !== null && node.contains(hit);
      }),
    ).toBe(true);
    const list = eight.locator("ol");
    expect(
      await list.evaluate((node) => node.scrollWidth > node.clientWidth),
    ).toBe(true);
  });
});

test("a move to another score waits for Apply, and Apply writes it as time", async ({
  page,
}) => {
  const writes: Array<{ method: string; url: string; body: unknown }> = [];
  await stubTiers(page, writes);
  await page.goto("/tiers/book");
  await page
    .getByRole("group", { name: "6", exact: true })
    .getByRole("button", { name: "Ficciones" })
    .click();
  await page
    .getByRole("group", { name: "7", exact: true })
    .getByRole("button", { name: "Place it here, as 7" })
    .click();
  const bar = page.getByRole("region", { name: "Changes to apply" });
  await expect(bar).toContainText("Ficciones 6 → 7");
  expect(writes).toEqual([]);
  await bar.getByRole("button", { name: "Apply 1 change" }).click();
  await expect.poll(() => writes.length).toBeGreaterThanOrEqual(2);
  expect(writes[0]).toEqual({
    method: "PATCH",
    url: "/api/entries/20",
    body: { score: 7, score_reason: "time" },
  });
});

test("a cover moves along its row and between rows from the keyboard", async ({
  page,
}) => {
  const writes: Array<{ method: string; url: string; body: unknown }> = [];
  await stubTiers(page, writes);
  await page.goto("/tiers/book");
  const piranesi = page.getByRole("button", { name: "Piranesi" });
  await piranesi.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowUp");
  await expect(
    page
      .getByRole("group", { name: "10", exact: true })
      .getByRole("button", { name: /Piranesi/ }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page
      .getByRole("group", { name: "9", exact: true })
      .getByRole("button", { name: "Piranesi" }),
  ).toBeVisible();
  expect(writes).toEqual([]);
});
