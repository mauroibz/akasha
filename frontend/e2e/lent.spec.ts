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

  const where = page.locator("[data-fact='location']");
  await where.getByRole("button", { name: "Change where it is" }).click();
  await where.getByRole("combobox", { name: "Where it is" }).fill("Hall");
  await where.getByRole("combobox", { name: "Where it is" }).press("Enter");
  await expect(where.locator("dd")).toContainText("Hall");

  const lent = page.locator("[data-fact='loan']");
  await lent.getByRole("button", { name: "Lend…" }).click();
  await expect(lent.getByRole("textbox", { name: "Lent on" })).toHaveValue(
    today(),
  );
  await lent.getByRole("combobox", { name: "Who has it" }).fill("Sofi");
  await lent.getByRole("button", { name: "Lend", exact: true }).click();
  await expect(lent).toContainText("To Sofi");

  await lent.getByRole("link", { name: "All lent" }).click();
  await expect(page.getByRole("heading", { name: "Lent out" })).toBeVisible();
  const row = page.getByRole("listitem").filter({ hasText: "Rayuela" });
  await expect(row).toContainText("Sofi");
  await row.getByRole("button", { name: "Rayuela is back" }).click();
  await expect(page.getByText("Nothing is lent out")).toBeVisible();
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("the rows and the list fit without scrolling sideways", async ({
    page,
  }) => {
    await stubHouse(page);
    await page.goto("/books/7");
    const lent = page.locator("[data-fact='loan']");
    await lent.getByRole("button", { name: "Lend…" }).click();
    await lent.getByRole("combobox", { name: "Who has it" }).fill("Sofi");
    await lent.getByRole("button", { name: "Lend", exact: true }).click();
    await expect(lent).toContainText("To Sofi");
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
