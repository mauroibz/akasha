import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppContent } from "./App";
import { AUTH_REQUIRED_EVENT } from "./api/request";

const admin = {
  id: 1,
  username: "mauro",
  display_name: "Mauro",
  is_admin: true,
};

function renderApp(initialEntry: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AppContent />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function libraryResponse(url: string) {
  if (url.includes("/api/auth/me")) {
    return new Response(
      JSON.stringify({
        auth: "on",
        authenticated: true,
        setup_required: false,
        user: admin,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/api/shelves")) {
    return new Response(
      JSON.stringify([
        {
          id: 1,
          name: "Favorites",
          slug: "favorites",
          entry_count: 0,
          covers: [],
          members_by_type: {},
        },
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/api/item-types")) {
    return new Response("[]", { status: 200 });
  }
  if (url.includes("/api/entries")) {
    return new Response(
      JSON.stringify({
        items: [],
        next_cursor: null,
        total: 0,
        facets: {
          status_counts: {},
          status_counts_by_type: {},
          format_counts: {},
        },
      }),
      { status: 200 },
    );
  }
  return new Response("{}", { status: 200 });
}

afterEach(() => vi.restoreAllMocks());

describe("authentication routing", () => {
  it("shows login before rendering a requested private address", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            auth: "on",
            authenticated: false,
            setup_required: false,
            user: null,
          }),
          { status: 200 },
        ),
      ),
    );

    renderApp("/shelves/favorites");

    expect(await screen.findByLabelText("Username")).toBeVisible();
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
  });

  it("keeps auth off invisible and redirects its auth addresses home", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input);
        if (url.includes("/api/auth/me")) {
          return new Response('{"detail":"Not Found"}', { status: 404 });
        }
        if (url.includes("/api/item-types") || url.includes("/api/shelves")) {
          return new Response("[]", { status: 200 });
        }
        return libraryResponse(url);
      }),
    );

    renderApp("/login");

    expect(await screen.findByText("Your library is waiting")).toBeVisible();
    expect(screen.queryByText("Sign out")).toBeNull();
    expect(screen.queryByLabelText("Username")).toBeNull();
  });

  it("routes a mid-session refusal to login and returns after success", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/auth/login")) {
        return new Response(JSON.stringify(admin), { status: 200 });
      }
      return libraryResponse(url);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp("/shelves/favorites");
    expect(
      await screen.findByRole("heading", { name: "Favorites" }),
    ).toBeVisible();

    act(() => {
      window.dispatchEvent(
        new CustomEvent(AUTH_REQUIRED_EVENT, {
          detail: { kind: "login" },
        }),
      );
    });
    expect(await screen.findByLabelText("Username")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Your session ended");

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "mauro");
    await user.type(screen.getByLabelText("Password"), "right password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { name: "Favorites" }),
    ).toBeVisible();
  });
});
