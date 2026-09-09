import type { Locator } from "@playwright/test";

import { expect, test } from "./console";
import { stubAuth } from "./auth-fixture";
import { bookItemType, entry, seedLibrary } from "./seed";

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

test("two people build two libraries without seeing each other's rows", async ({
  page,
}) => {
  const admin = {
    id: 1,
    username: "admin",
    display_name: "Mauro",
    is_admin: true,
  };
  const bruno = {
    id: 2,
    username: "bruno",
    display_name: "Bruno",
    is_admin: false,
  };
  let current: typeof admin | typeof bruno | null = admin;
  const people = [
    { ...admin, entry_count: 1, shelf_count: 0 },
    { ...bruno, entry_count: 0, shelf_count: 0 },
  ];
  const libraries = new Map<number, ReturnType<typeof entry>[]>([
    [1, [entry(3)]],
    [2, []],
  ]);

  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      json: {
        auth: "on",
        authenticated: Boolean(current),
        setup_required: false,
        user: current,
      },
    }),
  );
  await page.route("**/api/auth/session", async (route) => {
    current = null;
    await route.fulfill({ status: 204, body: "" });
  });
  await page.route("**/api/auth/login", async (route) => {
    const body = route.request().postDataJSON() as {
      username: string;
      password: string;
    };
    current =
      body.username === "bruno" && body.password === "bruno password"
        ? bruno
        : admin;
    await route.fulfill({ json: current });
  });
  await page.route("**/api/users", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 201, json: bruno });
      return;
    }
    await route.fulfill({ json: people });
  });
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [bookItemType] }),
  );
  await page.route("**/api/entries**", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as {
        manual: { title: string };
      };
      const created = entry(20);
      created.item.title = body.manual.title;
      libraries.get(current!.id)!.push(created);
      await route.fulfill({
        status: 201,
        json: { entry: created, already_exists: false, near_matches: [] },
      });
      return;
    }
    const items = libraries.get(current!.id)!;
    await route.fulfill({
      json: {
        items,
        next_cursor: null,
        total: items.length,
        facets: {
          status_counts: { read: items.length },
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    });
  });

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Mauro" }).first().click();
  await page.getByRole("button", { name: "People" }).click();
  await page.getByLabel("Username").fill("bruno");
  await page.getByLabel("Initial password").fill("bruno password");
  await page.getByRole("button", { name: "Create person" }).click();
  await page.getByRole("button", { name: "Mauro" }).first().click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Username").fill("bruno");
  await page.getByLabel("Password").fill("bruno password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Your library is waiting" }),
  ).toBeVisible();
  await expect(page.getByText("Seeded book 0003")).toHaveCount(0);
  await page.goto("/add");
  await page.getByLabel("Title", { exact: true }).fill("Ficciones");
  await page.getByRole("button", { name: "Add to library" }).click();
  await expect(page.getByRole("heading", { name: "Ficciones" })).toBeVisible();
  await expect(page.getByText("Seeded book 0003")).toHaveCount(0);
});
