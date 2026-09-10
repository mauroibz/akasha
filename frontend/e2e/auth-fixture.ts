import type { Page } from "@playwright/test";

export const authUser = {
  id: 1,
  username: "mauro",
  display_name: "Mauro",
  is_admin: true,
};

export const actingUser = {
  id: 2,
  username: "bruno",
  display_name: "Bruno",
  is_admin: false,
};

type AuthMode = "setup" | "anonymous" | "authenticated" | "acting";

/** Stateful auth boundary for browser tests; all other APIs remain real-shaped stubs. */
export async function stubAuth(page: Page, initial: AuthMode) {
  let setupRequired = initial === "setup";
  let authenticated = initial === "authenticated" || initial === "acting";
  let actingAs = initial === "acting" ? actingUser : null;
  let sessions = [
    {
      id: "current-browser",
      created_at: "2026-09-01T12:00:00Z",
      last_seen_at: "2026-09-10T12:00:00Z",
      user_agent: "Chromium on this device",
      current: true,
    },
    {
      id: "phone",
      created_at: "2026-08-01T12:00:00Z",
      last_seen_at: "2026-09-09T12:00:00Z",
      user_agent: "Mobile Safari",
      current: false,
    },
  ];

  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      json: {
        auth: "on",
        authenticated,
        setup_required: setupRequired,
        user: authenticated ? authUser : null,
        acting_as: authenticated ? actingAs : null,
      },
    }),
  );
  await page.route("**/api/auth/setup", async (route) => {
    setupRequired = false;
    authenticated = true;
    actingAs = null;
    await route.fulfill({ json: authUser });
  });
  await page.route("**/api/auth/login", async (route) => {
    const body = route.request().postDataJSON() as {
      username?: string;
      password?: string;
    };
    if (body.username === "mauro" && body.password === "right password") {
      authenticated = true;
      actingAs = null;
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
    actingAs = null;
    await route.fulfill({ status: 204, body: "" });
  });
  await page.route("**/api/auth/sessions/*", async (route) => {
    const id = new URL(route.request().url()).pathname.split("/").pop();
    const revoked = sessions.find((session) => session.id === id);
    sessions = sessions.filter((session) => session.id !== id);
    if (revoked?.current) authenticated = false;
    await route.fulfill({ status: 204, body: "" });
  });
  await page.route("**/api/auth/sessions", async (route) => {
    if (route.request().method() === "DELETE") {
      sessions = [];
      authenticated = false;
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await route.fulfill({ json: sessions });
  });
  await page.route("**/api/auth/act-as/**", async (route) => {
    actingAs = actingUser;
    await route.fulfill({ status: 204, body: "" });
  });
  await page.route("**/api/auth/act-as", async (route) => {
    actingAs = null;
    await route.fulfill({ status: 204, body: "" });
  });

  return {
    expire() {
      authenticated = false;
      actingAs = null;
    },
  };
}
