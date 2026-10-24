import { expect, test } from "./console";
import { stubHouse, today } from "./house-fixture";

/**
 * Where a thing is and who has it (Sprint 111, DEC-176): the detail page's *Where* and
 * *Lent* rows, and `/lent`. The server is stubbed statefully, as the real one answers.
 */

test("a thing is placed, lent, listed as out, and comes back", async ({
  page,
}) => {
  await stubHouse(page);
  await page.goto("/books/7");

  // Nothing recorded yet: no row, a question (Sprint 124).
  await expect(page.locator("[data-fact='location']")).toHaveCount(0);
  const question = page.locator("[data-question]");
  while ((await question.getAttribute("data-question")) !== "location")
    await question.getByRole("button", { name: "Skip" }).click();
  await question.getByRole("textbox", { name: "Where it is" }).fill("Hall");
  await question.getByRole("button", { name: "Save" }).click();
  const where = page.locator("[data-fact='location']");
  await expect(where.locator("dd")).toContainText("Hall");

  await expect(page.locator("[data-fact='loan']")).toHaveCount(0);
  await page.getByRole("button", { name: "Lend…" }).click();
  const lent = page.locator("[data-fact='loan']");
  await expect(lent.getByRole("textbox", { name: "Lent on" })).toHaveValue(
    today(),
  );
  await lent.getByRole("combobox", { name: "Who has it" }).fill("Sofi");
  await lent.getByRole("button", { name: "Lend", exact: true }).click();
  await expect(lent).toContainText("To Sofi");

  await expect(lent.getByRole("link", { name: "All lent" })).toBeVisible();

  // What is out stands on the shelves (Sprint 122), and opens the list.
  await page.goto("/shelves");
  const ledge = page.locator("[data-shelf-row='lent']");
  await expect(ledge).toContainText("Rayuela has been with Sofi since today");
  await ledge.getByRole("link", { name: "Lent out" }).click();
  await expect(page.getByRole("heading", { name: "Lent out" })).toBeVisible();
  await expect(page.getByRole("link", { name: "← Shelves" })).toBeVisible();
  const row = page.getByRole("listitem").filter({ hasText: "Rayuela" });
  await expect(row).toContainText("Sofi");
  await row.getByRole("button", { name: "Rayuela is back" }).click();
  await expect(page.getByText("Nothing is lent out")).toBeVisible();
  await page.getByRole("link", { name: "← Shelves" }).click();
  await expect(page.locator("[data-shelf-row='lent']")).toHaveCount(0);
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("the rows and the list fit without scrolling sideways", async ({
    page,
  }) => {
    await stubHouse(page);
    await page.goto("/books/7");
    await page.getByRole("button", { name: "Lend…" }).click();
    const lent = page.locator("[data-fact='loan']");
    await lent.getByRole("combobox", { name: "Who has it" }).fill("Sofi");
    await lent.getByRole("button", { name: "Lend", exact: true }).click();
    await expect(lent).toContainText("To Sofi");
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await page.goto("/shelves");
    await expect(page.locator("[data-shelf-row='lent']")).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await page.goto("/lent");
    await expect(page.getByRole("listitem")).toHaveCount(1);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
  });
});
