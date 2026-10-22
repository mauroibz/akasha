import { expect, test } from "./console";

import { bookType, stubSeries } from "./progress-fixture";
import { entry as seededEntry, seedLibrary } from "./seed";

/**
 * Episodes and chapters on the detail page (Sprint 108, DEC-171), and the question
 * asked when an entry is dropped (DEC-172). The server is stubbed statefully: a
 * `PATCH` with marks stores them and sets the count, as the real one does.
 */

test("a season is ticked off on the detail page, one episode and then all of it", async ({
  page,
}) => {
  const patches: unknown[] = [];
  await stubSeries(page, patches);
  await page.goto("/books/7");

  const row = page.locator("[data-fact='progress']");
  await expect(row.getByText("3 / 7 episodes")).toBeVisible();
  const line = page.getByRole("button", { name: /Show episodes/ });
  await expect(line).toHaveAttribute("aria-expanded", "false");
  await line.click();
  // An imported count of three is drawn as the first season.
  await expect(
    page.getByRole("button", { name: "Season 1, episode 3" }),
  ).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Season 2, episode 1" }).click();
  await expect(row.getByText("4 / 7 episodes")).toBeVisible();
  await page.getByRole("button", { name: "Mark all of season 2" }).click();
  await expect(row.getByText("7 / 7 episodes")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Clear season 2" }),
  ).toBeVisible();
  // The last light finishes the entry, where the date was empty (DEC-175).
  const now = new Date();
  const day = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
  expect(patches).toEqual([
    { progress_marks: { "1": [1, 2, 3], "2": [1] } },
    {
      progress_marks: { "1": [1, 2, 3], "2": [1, 2, 3, 4] },
      date_finished: day,
    },
  ]);
  await expect(page.locator("[data-fact='finished'] dd")).toContainText(day);
  // The parts field is the tracker's, not a second table.
  await expect(page.getByText("Episodes per season")).toHaveCount(0);
});

test("the arrow keys move between the lights", async ({ page }) => {
  await stubSeries(page, []);
  await page.goto("/books/7");
  await page.getByRole("button", { name: /Show episodes/ }).click();
  // The tab stop is the first episode not yet watched.
  const first = page.getByRole("button", { name: "Season 2, episode 1" });
  await first.focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("button", { name: "Season 2, episode 2" }),
  ).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await expect(
    page.getByRole("button", { name: "Season 1, episode 2" }),
  ).toBeFocused();
});

test("dropping from the detail page asks how far, and a tap saves through it", async ({
  page,
}) => {
  const patches: unknown[] = [];
  await stubSeries(page, patches);
  await page.goto("/books/7");
  await page.getByRole("button", { name: /edit opinion/i }).click();
  await page.getByRole("combobox", { name: "Status" }).click();
  await page.getByRole("option", { name: "Dropped", exact: true }).click();
  await page.getByRole("button", { name: "Save" }).click();

  const asked = page.getByRole("dialog", { name: "How far did you get?" });
  await expect(asked).toBeVisible();
  await asked.getByRole("button", { name: "Season 2, episode 2" }).click();
  await expect(asked.getByText("5 of 7 episodes")).toBeVisible();
  await asked.getByRole("button", { name: "Save" }).click();
  await expect(asked).toBeHidden();

  // The status save carried no count, so it could not clear any marks.
  expect((patches[0] as Record<string, unknown>).status).toBe("dropped");
  expect(patches[0]).not.toHaveProperty("progress");
  expect(patches.at(-1)).toEqual({
    progress_marks: { "1": [1, 2, 3], "2": [1, 2] },
  });
});

test("dropping from a library row asks too, and Skip saves nothing more", async ({
  page,
}) => {
  const patches: unknown[] = [];
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [bookType] }),
  );
  await page.route("**/api/entries/1", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    patches.push(body);
    const book = seededEntry(1);
    await route.fulfill({
      json: {
        ...book,
        ...body,
        progress: null,
        item: {
          ...book.item,
          metadata: { chapters: 12 },
          outline: [{ part: 1, size: 12 }],
        },
      },
    });
  });
  await seedLibrary(page, 3);
  await page.goto("/");
  const card = page.locator("[data-entry-id='1']");
  await card.getByRole("combobox").click();
  await page.getByRole("option", { name: "Dropped", exact: true }).click();

  const asked = page.getByRole("dialog", { name: "How far did you get?" });
  await expect(asked).toBeVisible();
  await expect(asked.getByRole("button", { name: "Chapter 12" })).toBeVisible();
  await asked.getByRole("button", { name: "Skip" }).click();
  await expect(asked).toBeHidden();
  expect(patches).toEqual([{ status: "dropped" }]);
});

test("the tracker fits a phone without scrolling sideways", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stubSeries(page, []);
  await page.goto("/books/7");
  await page.getByRole("button", { name: /Show episodes/ }).click();
  await expect(
    page.getByRole("button", { name: "Season 2, episode 4" }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
