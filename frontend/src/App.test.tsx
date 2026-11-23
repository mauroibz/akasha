import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppContent } from "./App";
import { AUTH_REQUIRED_EVENT } from "./api/request";

const admin = {
  id: 1,
  username: "mauro",
  display_name: "Mauro",
  is_admin: true,
};

/** Where the router ended up, so a redirect can be asserted rather than inferred. */
function LocationProbe() {
  const location = useLocation();
  return (
    <div data-testid="location">{`${location.pathname}${location.search}`}</div>
  );
}

function renderApp(initialEntry: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AppContent />
        <LocationProbe />
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
      vi.fn(
        async () =>
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

  it("keeps password login available when a proxy identity is unknown", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                code: "unknown_proxy_identity",
                message: "This proxy identity is not allowed to use Akasha",
                details: {},
              },
            }),
            { status: 403 },
          ),
      ),
    );

    renderApp("/");

    expect(await screen.findByLabelText("Username")).toBeVisible();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeVisible();
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
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/$/);
    expect(screen.queryByText("Sign out")).toBeNull();
    expect(screen.queryByLabelText("Username")).toBeNull();
  });

  it("sends every address to first-run setup until the library is claimed", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return new Response(
          JSON.stringify({
            auth: "on",
            authenticated: false,
            setup_required: true,
            user: null,
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/auth/setup")) {
        return new Response(JSON.stringify(admin), { status: 200 });
      }
      return libraryResponse(url);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp("/shelves/favorites");

    expect(
      await screen.findByRole("button", { name: "Claim library" }),
    ).toBeVisible();
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "mauro");
    await user.type(screen.getByLabelText("Display name"), "Mauro");
    await user.type(screen.getByLabelText("Password"), "right password");
    await user.type(screen.getByLabelText("Setup code"), "k7mq-3xwd-p9hz");
    await user.click(screen.getByRole("button", { name: "Claim library" }));

    expect(
      await screen.findByRole("heading", { name: "Favorites" }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).includes("/api/auth/me"),
      ),
    ).toHaveLength(1);
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

    // Several queries can discover one expired cookie together. The first
    // refusal owns the destination; a later one arriving after the login route
    // mounted must not replace it with `/login`.
    act(() => {
      window.dispatchEvent(
        new CustomEvent(AUTH_REQUIRED_EVENT, {
          detail: { kind: "login" },
        }),
      );
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "mauro");
    await user.type(screen.getByLabelText("Password"), "right password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { name: "Favorites" }),
    ).toBeVisible();
  });
});

function authOff(url: string) {
  if (url.includes("/api/auth/me")) {
    return new Response('{"detail":"Not Found"}', { status: 404 });
  }
  return libraryResponse(url);
}

describe("the library is the home (Sprint 141, DEC-193)", () => {
  it("opens on the Library at /", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => authOff(String(input))),
    );
    renderApp("/");

    expect(await screen.findByText("Your library is waiting")).toBeVisible();
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/$/);
  });

  it("sends the old /library address to / with the filters it carried", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => authOff(String(input))),
    );
    renderApp("/library?type=anime&status=watching");

    expect(await screen.findByText("Your library is waiting")).toBeVisible();
    expect(screen.getByTestId("location")).toHaveTextContent(
      "/?type=anime&status=watching",
    );
  });

  it("puts the Library first in the navigation, at /, with no Home beside it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => authOff(String(input))),
    );
    renderApp("/");
    await screen.findByText("Your library is waiting");

    const [desktop] = screen.getAllByRole("navigation", { name: "Primary" });
    const links = Array.from(desktop.querySelectorAll("a"));
    expect(links[0]).toHaveAttribute("href", "/");
    expect(links[0]).toHaveTextContent("Library");
    expect(links.some((link) => link.textContent === "Home")).toBe(false);
  });
});
