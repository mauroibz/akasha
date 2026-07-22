import { expect, test } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

const mode = process.env.LIVE_METADATA_MODE;
test.skip(
  !mode,
  "requires an explicitly started live backend and provider network access",
);
test.describe.configure({ mode: "serial" });

const books = [
  { query: "100 años de soledad", author: /Gabriel García Márquez/i },
  {
    query: "Harry Potter y la piedra filosofal",
    author: /J\. K\. Rowling|J\.K\. Rowling/i,
  },
  { query: "La sombra del viento", author: /Carlos Ruiz Zafón/i },
];

test("live provider editions add with metadata and cached covers", async ({
  page,
}) => {
  test.skip(mode !== "add");
  const saved: Array<{ url: string; title: string; editionYear: string }> = [];
  for (const book of books) {
    await page.goto("/add");
    await page
      .getByRole("searchbox", { name: /search books/i })
      .fill(book.query);
    const result = page
      .getByRole("button", { name: book.author })
      .filter({ hasText: /Edition year:\s*\d{4}/ })
      .first();
    await expect(result).toBeVisible({ timeout: 15_000 });
    await expect(result.locator("img")).toBeVisible();
    await expect(result).toContainText(/Edition year:\s*\d{4}/);
    await result.click();
    await page.getByRole("button", { name: /add to library/i }).click();
    await expect(page).toHaveURL(/\/books\/\d+/, { timeout: 20_000 });
    await expect(page.locator("main img").first()).toBeVisible();
    await expect(page.getByText(/Edition year:/)).toBeVisible();
    const detailText = await page.locator("main").textContent();
    const editionYear =
      detailText?.match(/Edition year:\s*(\d{4})/)?.[1] ?? "unknown";
    expect(editionYear).not.toBe("unknown");
    saved.push({
      url: new URL(page.url()).pathname,
      title: book.query,
      editionYear,
    });
  }
  writeFileSync("/tmp/akasha-live-entries.json", JSON.stringify(saved));
});

test("saved editions render after an offline backend restart", async ({
  page,
}) => {
  test.skip(mode !== "offline");
  const saved = JSON.parse(
    readFileSync("/tmp/akasha-live-entries.json", "utf8"),
  ) as Array<{
    url: string;
    title: string;
  }>;
  for (const book of saved) {
    await page.goto(book.url);
    await expect(page.locator("main img").first()).toBeVisible();
    await expect(page.getByText(/Edition year:/)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /refresh from provider/i }),
    ).toBeVisible();
  }
});
