import type { Page } from "@playwright/test";

import { stubChores } from "./chores-fixture";
import { expect, test } from "./console";

/**
 * The deck for any chore (Sprint 112, DEC-176): *Still want this?* and *Find a cover*
 * on the shared deck, at a phone's and a desktop's size.
 */

async function expectOnScreen(page: Page, names: string[]) {
  const viewport = page.viewportSize()!;
  for (const name of [...names, "card"]) {
    const locator =
      name === "card"
        ? page.locator("[data-deck-card]")
        : page.getByRole("button", { name, exact: true });
    const box = (await locator.boundingBox())!;
    expect(box, name).not.toBeNull();
    expect(box.y, `${name} top`).toBeGreaterThanOrEqual(0);
    expect(box.y + box.height, `${name} bottom`).toBeLessThanOrEqual(
      viewport.height,
    );
    expect(box.x + box.width, `${name} right`).toBeLessThanOrEqual(
      viewport.width,
    );
  }
  const title = page.getByTestId("deck-title");
  expect(
    await title.evaluate((node) => node.scrollHeight <= node.clientHeight + 1),
  ).toBe(true);
}

for (const size of [
  { name: "a phone", width: 390, height: 664 },
  { name: "a desktop", width: 1440, height: 900 },
]) {
  test(`on ${size.name} both chores fit without scrolling`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: size.width, height: size.height });
    await stubChores(page);
    await page.goto("/deck/planned");
    await expect(page.getByTestId("deck-title")).toHaveText("Stoner");
    await expectOnScreen(page, ["Later", "Let go", "Keep"]);
    await page.getByRole("button", { name: "Keep", exact: true }).click();
    await expect(page.getByTestId("deck-title")).toContainText(
      "Remains of the Day",
    );
    await expectOnScreen(page, ["Later", "Let go", "Keep"]);

    await page.goto("/deck/duplicates");
    await expect(
      page.getByRole("group", { name: "Stoner", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Keep this one" }).first().click();
    const viewport = page.viewportSize()!;
    for (const name of ["Later", "They’re different", "Merge"]) {
      const box = (await page
        .getByRole("button", { name, exact: true })
        .boundingBox())!;
      expect(box.y + box.height, `${name} bottom`).toBeLessThanOrEqual(
        viewport.height,
      );
      expect(box.x + box.width, `${name} right`).toBeLessThanOrEqual(
        viewport.width,
      );
    }
    const card = (await page.locator("[data-deck-card]").boundingBox())!;
    expect(card.y).toBeGreaterThanOrEqual(0);

    await page.goto("/deck/revisit");
    await expect(page.getByTestId("deck-title")).toHaveText("Stoner");
    await expectOnScreen(page, ["Later", "Keep 9", "Score 10"]);

    await page.goto("/deck/covers");
    await expect(page.getByTestId("deck-title")).toHaveText("Stoner");
    await expect(
      page.getByRole("button", { name: "The 1965 edition's cover" }),
    ).toBeVisible();
    await expectOnScreen(page, [
      "Later",
      "Use this cover",
      "The 1965 edition's cover",
    ]);
  });
}

test("what is let go is removed only after the end asks once", async ({
  page,
}) => {
  const calls: Array<{ method: string; url: string; body: unknown }> = [];
  await stubChores(page, calls);
  await page.goto("/deck");
  await page.getByRole("link", { name: /Still want this/ }).click();
  await expect(page.getByTestId("deck-title")).toHaveText("Stoner");
  await page.getByRole("button", { name: "Let go", exact: true }).click();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("x");
  await expect(
    page.getByRole("button", { name: "Remove the 2 you let go" }),
  ).toBeVisible();
  expect(calls).toEqual([]);
  await page.getByRole("button", { name: "Remove the 2 you let go" }).click();
  const confirm = page.getByRole("alertdialog");
  await expect(confirm).toContainText("Stoner, Ficciones");
  await confirm.getByRole("button", { name: "Remove 2" }).click();
  await expect(page.getByText(/Removed 1/)).toBeVisible();
  expect(calls).toEqual([
    { method: "DELETE", url: "/api/entries/bulk", body: { entry_ids: [1, 3] } },
  ]);
});

test("a cover is chosen and installed", async ({ page }) => {
  const calls: Array<{ method: string; url: string; body: unknown }> = [];
  await stubChores(page, calls);
  await page.goto("/deck/covers");
  await page.getByRole("button", { name: "The 1965 edition's cover" }).click();
  await page.getByRole("button", { name: "Use this cover" }).click();
  await expect(page.getByText("Every one has a cover")).toBeVisible();
  expect(calls).toHaveLength(1);
  expect(calls[0]).toMatchObject({
    method: "POST",
    url: "/api/items/101/cover",
  });
});

test("two editions are merged into the one kept", async ({ page }) => {
  const calls: Array<{ method: string; url: string; body: unknown }> = [];
  await stubChores(page, calls);
  await page.goto("/deck/duplicates");
  const kept = page.getByRole("group", {
    name: "Stoner (New York Review Books Classics)",
  });
  await kept.getByRole("button", { name: "Keep this one" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "is removed" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Merge", exact: true }).click();
  await expect(page.getByText("No duplicates left")).toBeVisible();
  expect(calls).toEqual([
    {
      method: "POST",
      url: "/api/duplicates/merge",
      body: { keep: 4, drop: 1 },
    },
  ]);
});

test("an old score kept is written as a look, with why", async ({ page }) => {
  const calls: Array<{ method: string; url: string; body: unknown }> = [];
  await stubChores(page, calls);
  await page.goto("/deck/revisit");
  await expect(page.getByRole("heading", { name: "Still a 9?" })).toBeVisible();
  await page.getByRole("button", { name: "Keep 9" }).click();
  await expect(page.getByText("Every old score looked at")).toBeVisible();
  expect(calls).toEqual([
    {
      method: "PATCH",
      url: "/api/entries/1",
      body: { score: 9, score_reason: "time" },
    },
  ]);
});
