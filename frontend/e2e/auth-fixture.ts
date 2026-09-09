import type { Page } from "@playwright/test";

export const authUser = {
  id: 1,
  username: "mauro",
  display_name: "Mauro",
  is_admin: true,
};

type AuthMode = "setup" | "anonymous" | "authenticated";

/** Stateful auth boundary for browser tests; all other APIs remain real-shaped stubs. */
export async function stubAuth(page: Page, initial: AuthMode) {
  let setupRequired = initial === "setup";
  let authenticated = initial === "authenticated";

  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      json: {
        auth: "on",
        authenticated,
        setup_required: setupRequired,
        user: authenticated ? authUser : null,
      },
    }),
  );
  await page.route("**/api/auth/setup", async (route) => {
    setupRequired = false;
    authenticated = true;
    await route.fulfill({ json: authUser });
  });
  await page.route("**/api/auth/login", async (route) => {
    const body = route.request().postDataJSON() as {
      username?: string;
      password?: string;
    };
    if (body.username === "mauro" && body.password === "right password") {
      authenticated = true;
      await route.fulfill({ json: authUser });
      return;
    }
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
  });
  await page.route("**/api/auth/session", async (route) => {
    authenticated = false;
    await route.fulfill({ status: 204, body: "" });
  });

  return {
    expire() {
      authenticated = false;
    },
  };
}
