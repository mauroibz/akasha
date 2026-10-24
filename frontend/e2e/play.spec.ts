import { expect, test } from "./console";
import { stubPlay } from "./play-fixture";

/**
 * Play with your library (Sprint 125, DEC-179): the games at the top of Insights, and
 * Fill in the gaps, one book at a time.
 */

test("Insights opens with games about your own books", async ({ page }) => {
  await stubPlay(page);
  await page.goto("/insights");
  const play = page.getByRole("region", { name: "Play with your library" });
  await expect(play).toBeVisible();
  await expect(
    play.getByRole("link", { name: /Which 10 is your best 10\?/ }),
  ).toBeVisible();
  await expect(
    play.getByRole("link", { name: /Is Stoner still a 9\?/ }),
  ).toBeVisible();
  await play.getByRole("link", { name: /The pile/ }).click();
  await expect(page.getByTestId("deck-title")).toHaveText("Stoner");
});

test("the gaps are filled one book at a time", async ({ page }) => {
  const calls: Array<{ method: string; url: string; body: unknown }> = [];
  await stubPlay(page, calls);
  await page.goto("/insights");
  await page
    .getByRole("region", { name: "Play with your library" })
    .getByRole("link", { name: /Fill in the gaps/ })
    .click();
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  const question = page.locator("[data-question]");
  await expect(question).toHaveAttribute("data-question", "date_finished");
  await question.getByLabel("Date").fill("2019-05-01");
  await question.getByRole("button", { name: "Save" }).click();
  await expect(question).toHaveAttribute("data-question", "formats");
  expect(calls).toContainEqual({
    method: "PATCH",
    url: "/api/entries/7",
    body: { date_finished: "2019-05-01" },
  });
  await page.getByRole("button", { name: "Next book" }).click();
  await expect(page.getByRole("heading", { name: "Ficciones" })).toBeVisible();
  await page.getByRole("button", { name: "I don't remember" }).click();
  await page.getByRole("button", { name: "Next book" }).click();
  await expect(page.getByText("That's every gap for now")).toBeVisible();
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 664 } });

  test("Play and the gaps fit without scrolling sideways", async ({ page }) => {
    await stubPlay(page);
    await page.goto("/insights");
    await expect(
      page.getByRole("region", { name: "Play with your library" }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await page.goto("/play/gaps");
    await expect(page.locator("[data-question]")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Next book" }),
    ).toBeInViewport();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
  });
});
