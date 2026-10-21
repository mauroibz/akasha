import { expect, test } from "./console";
import { bookItemType, seedLibrary, stubItemTypes } from "./seed";

// Sprint 094: the one door. Opened from anywhere, it finds in the library,
// searches the web with an explicit Add, and goes places, all from the keyboard.
test("the command bar finds, adds and navigates from the keyboard", async ({
  page,
}) => {
  await seedLibrary(page, 3);
  await stubItemTypes(page, [bookItemType]);
  const posted: unknown[] = [];
  await page.route("**/api/search/library?**", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/search?**", (route) =>
    route.fulfill({
      json: [
        {
          source: "openlibrary",
          source_id: "OL1M",
          source_refs: [{ source: "openlibrary", source_id: "OL1M" }],
          title: "Ficciones",
          subtitle: null,
          creators: ["Jorge Luis Borges"],
          credit: null,
          year: 1944,
          cover_url: null,
          identifiers: {},
          language: "es",
          metadata: {},
        },
      ],
    }),
  );
  await page.route("**/api/entries", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    posted.push(route.request().postDataJSON());
    await route.fulfill({
      status: 201,
      json: {
        entry: { id: 99, item: { title: "Ficciones" } },
        already_exists: false,
        near_matches: [],
      },
    });
  });

  await page.goto("/");
  await expect(page.getByRole("feed", { name: "Library" })).toBeVisible();
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByRole("combobox", { name: "Search or add" });
  await expect(input).toBeFocused();

  await input.fill("ficciones");
  const result = page.getByRole("option", { name: /Ficciones/ });
  await expect(result).toBeVisible();
  await page.keyboard.press("Enter");
  await expect.poll(() => posted.length).toBe(1);
  await expect(page.getByText("Added · Open")).toBeVisible();

  await input.fill("insights");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/insights$/);
});
