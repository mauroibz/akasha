import { expect, test } from "./console";
import { stubRescore } from "./rescore-fixture";

/**
 * Another time through, and "Still an 8?" (Sprint 115, DEC-176): the pass starts
 * again from the detail page, the last light finishes it, and the question records
 * the answer in the score's history, which the page then shows.
 */

test("a reread starts, finishes on the last light, and its new score joins the history", async ({
  page,
}) => {
  const patches: Array<Record<string, unknown>> = [];
  await stubRescore(page, patches);
  await page.goto("/books/7");
  await expect(page.locator("[data-fact='score-history']")).toHaveCount(0);

  await page.getByRole("button", { name: "Start again" }).click();
  const confirm = page.getByRole("alertdialog");
  await expect(confirm).toContainText("2019-05-01");
  await confirm.getByRole("button", { name: "Start again" }).click();
  await expect(page.locator("[data-fact='status'] dd")).toContainText(
    "Reading",
  );

  await page.getByRole("button", { name: /Show chapters/ }).click();
  for (const chapter of [1, 2, 3])
    await page
      .getByRole("button", { name: `Chapter ${chapter}`, exact: true })
      .click();

  const still = page.getByRole("dialog", { name: "Still an 8?" });
  await expect(still).toBeVisible();
  await still.getByRole("button", { name: "Score 9" }).click();
  await still.getByRole("textbox").fill("The hopscotch order this time");
  await still.getByRole("button", { name: "Change to 9" }).click();
  await expect(still).toBeHidden();

  expect(patches.at(-1)).toEqual({
    score: 9,
    score_reason: "reread",
    score_note: "The hopscotch order this time",
  });
  const row = page.locator("[data-fact='score-history']");
  await expect(row).toContainText("8 in 2019");
  await row.getByRole("button", { name: "Why" }).click();
  await expect(row).toContainText("after a reread");
  await expect(row).toContainText("The hopscotch order this time");
});
