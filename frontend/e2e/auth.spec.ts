import type { Locator } from "@playwright/test";

import { expect, test } from "./console";
import { stubAuth } from "./auth-fixture";
import { entry, seedLibrary } from "./seed";

const favorite = {
  id: 1,
  name: "Favorites",
  slug: "favorites",
  entry_count: 1,
  covers: [],
  members_by_type: { book: 1 },
};

async function expectFocusRing(control: Locator) {
  const shadow = await control.evaluate(
    (node) => getComputedStyle(node).boxShadow,
  );
  expect(shadow).not.toBe("none");
}

test("first-run setup claims the library by keyboard at 390px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stubAuth(page, "setup");
  await seedLibrary(page, 3);
  await page.goto("/");

  await expect(page).toHaveURL(/\/setup$/);
  await expect(
    page.getByText(/claims the library already on this install/i),
  ).toBeVisible();
  for (const control of [
    page.getByLabel("Username"),
    page.getByLabel("Display name"),
    page.getByLabel("Password"),
    page.getByRole("button", { name: "Claim library" }),
  ]) {
    expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }

  await expect(page.getByLabel("Username")).toBeFocused();
  await expectFocusRing(page.getByLabel("Username"));
  await page.keyboard.type("mauro");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Display name")).toBeFocused();
  await expectFocusRing(page.getByLabel("Display name"));
  await page.keyboard.type("Mauro");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await expectFocusRing(page.getByLabel("Password"));
  await page.keyboard.type("right password");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Claim library" }),
  ).toBeFocused();
  await expectFocusRing(page.getByRole("button", { name: "Claim library" }));
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();
});

test("login returns to the private address that was requested", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stubAuth(page, "anonymous");
  await seedLibrary(page, 1);
  await page.route("**/api/shelves", (route) =>
    route.fulfill({ json: [favorite] }),
  );
  await page.goto("/shelves/favorites");

  await expect(page).toHaveURL(/\/login$/);
  const username = page.getByLabel("Username");
  const password = page.getByLabel("Password");
  const submit = page.getByRole("button", { name: "Sign in" });
  await expect(username).toHaveAttribute("autocomplete", "username");
  await expect(password).toHaveAttribute("autocomplete", "current-password");
  for (const control of [username, password, submit]) {
    expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  await expect(username).toBeFocused();
  await expectFocusRing(username);
  await page.keyboard.type("mauro");
  await page.keyboard.press("Tab");
  await expect(password).toBeFocused();
  await expectFocusRing(password);
  await page.keyboard.type("right password");
  await page.keyboard.press("Tab");
  await expect(submit).toBeFocused();
  await expectFocusRing(submit);
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/\/shelves\/favorites$/);
  await expect(page.getByRole("heading", { name: "Favorites" })).toBeVisible();
});

test("sign out cannot be undone with browser back", async ({ page }) => {
  await stubAuth(page, "authenticated");
  await seedLibrary(page, 1);
  await page.route("**/api/shelves", (route) =>
    route.fulfill({ json: [favorite] }),
  );
  await page.goto("/");
  await page.goto("/shelves/favorites");
  await expect(page.getByRole("heading", { name: "Favorites" })).toBeVisible();

  await page.getByRole("button", { name: "Mauro" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goBack();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Favorites" })).toHaveCount(0);
  await expect(page.getByLabel("Username")).toBeVisible();
});

test("a mid-session 401 closes an open dialog and asks for login", async ({
  page,
}) => {
  const auth = await stubAuth(page, "authenticated");
  const detail = entry(7);
  await page.route("**/api/entries/7", async (route) => {
    if (route.request().method() === "PATCH") {
      auth.expire();
      await route.fulfill({
        status: 401,
        json: {
          error: {
            code: "unauthenticated",
            message: "Authentication is required",
            details: {},
          },
        },
      });
      return;
    }
    await route.fulfill({ json: detail });
  });
  await page.route("**/api/items/7/attachments", (route) =>
    route.fulfill({ json: { attachments: [] } }),
  );
  await page.goto("/books/7");
  await page.getByRole("button", { name: /edit opinion/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible();

  await page.getByRole("button", { name: "Save opinion" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText("Your session ended");
});
