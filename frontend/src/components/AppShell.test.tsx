import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/AppShell";
import { NotFoundPage } from "@/pages/NotFoundPage";

function renderShell(routes: React.ReactNode) {
  // The shell reads the Inbox count since Sprint 096, as the app always provides.
  if (!vi.isMockFunction(globalThis.fetch))
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response(JSON.stringify({ items: [], total: 0 })),
    );
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/"]}>
        <AppShell>{routes}</AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("AppShell", () => {
  it("renders Home, Library, Add, Import, and Shelves navigation links", () => {
    renderShell(
      <Routes>
        <Route path="/" element={<div>Library page</div>} />
        <Route path="/add" element={<div>Add page</div>} />
        <Route path="/import" element={<div>Import page</div>} />
        <Route path="/shelves" element={<div>Shelves page</div>} />
      </Routes>,
    );
    // Both desktop and mobile navs exist in the DOM; in jsdom the hidden class
    // removes the desktop nav from the accessibility tree, so check all links.
    for (const label of ["Home", "Library", "Add", "Import", "Shelves"]) {
      const links = screen.getAllByRole("link", {
        name: new RegExp(label, "i"),
      });
      expect(links.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("highlights the active route via aria-current", () => {
    renderShell(
      <Routes>
        <Route path="/" element={<div>Library page</div>} />
        <Route path="/add" element={<div>Add page</div>} />
      </Routes>,
    );
    // `/` is Home since Sprint 130; the library is `/library` and not current here.
    const homeLinks = screen.getAllByRole("link", { name: /^home$/i });
    expect(homeLinks.find((l) => l.hasAttribute("aria-current"))).toBeDefined();
    for (const link of screen.getAllByRole("link", { name: /^library$/i })) {
      expect(link.hasAttribute("aria-current")).toBe(false);
    }
    const addLinks = screen.getAllByRole("link", { name: /^add$/i });
    for (const link of addLinks) {
      expect(link.hasAttribute("aria-current")).toBe(false);
    }
  });

  it("keeps the phone's bar to five, Home first and Import off it", () => {
    renderShell(
      <Routes>
        <Route path="/" element={<div>Home page</div>} />
      </Routes>,
    );
    const [, phone] = screen.getAllByRole("navigation", {
      name: "Primary",
      hidden: true,
    });
    const labels = Array.from(phone.querySelectorAll("a")).map((link) =>
      link.getAttribute("aria-label"),
    );
    expect(labels).toEqual(["Home", "Library", "Add", "Shelves", "Insights"]);
  });

  it("shows a useful 404 for unknown routes", () => {
    render(
      <MemoryRouter initialEntries={["/nonexistent"]}>
        <Routes>
          <Route path="/" element={<div>Home</div>} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /not found/i })).toBeVisible();
    expect(
      screen.getByRole("button", { name: /go to library/i }),
    ).toBeVisible();
  });

  it("shows the signed-in person and signs their session out", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const onSignedOut = vi.fn();
    const user = userEvent.setup();

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/"]}>
          <AppShell
            user={{
              id: 1,
              username: "mauro",
              display_name: "Mauro",
              is_admin: true,
            }}
            onSignedOut={onSignedOut}
          >
            <Routes>
              <Route path="/" element={<div>Library page</div>} />
              <Route path="/login" element={<h1>Sign-in destination</h1>} />
            </Routes>
          </AppShell>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.click(screen.getAllByRole("button", { name: "Mauro" })[0]);
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(
      await screen.findByRole("heading", { name: "Sign-in destination" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/session", {
      method: "DELETE",
    });
    expect(onSignedOut).toHaveBeenCalledOnce();
  });

  it("keeps an announced acting-as banner above the app and leaves in one press", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const onActingAsChanged = vi.fn();
    const user = userEvent.setup();

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/books/7"]}>
          <AppShell
            user={{
              id: 1,
              username: "mauro",
              display_name: "Mauro",
              is_admin: true,
            }}
            actingAs={{
              id: 2,
              username: "bruno",
              display_name: "Bruno",
              is_admin: false,
            }}
            onActingAsChanged={onActingAsChanged}
            onSignedOut={vi.fn()}
          >
            <Routes>
              <Route path="/library" element={<h1>Own library</h1>} />
              <Route
                path="/books/7"
                element={<div role="dialog">Edit entry</div>}
              />
            </Routes>
          </AppShell>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const banner = screen.getByRole("status", {
      name: "Viewing Bruno's library",
    });
    expect(banner).toHaveAttribute("aria-live", "polite");
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(
      screen.getAllByRole("button", { name: "Mauro" }).length,
    ).toBeGreaterThan(0);

    await user.click(
      screen.getByRole("button", { name: "Return to your library" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Own library" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/act-as", {
      method: "DELETE",
    });
    expect(onActingAsChanged).toHaveBeenCalledWith(null);
  });

  it("recounts the Inbox when a background job finishes, not on a timer", async () => {
    const sources: { emit: (state: string) => void }[] = [];
    vi.stubGlobal(
      "EventSource",
      class {
        listener: ((message: MessageEvent<string>) => void) | null = null;
        constructor() {
          sources.push({
            emit: (state) =>
              this.listener?.({
                data: JSON.stringify({
                  id: "j1",
                  batch_id: null,
                  kind: "search_import_rows",
                  state,
                  progress: {},
                  error: null,
                  error_code: null,
                  attempts: 0,
                  updated_at: new Date().toISOString(),
                }),
              } as MessageEvent<string>),
          });
        }
        addEventListener(
          _type: string,
          listener: (message: MessageEvent<string>) => void,
        ) {
          this.listener = listener;
        }
        removeEventListener() {}
        close() {}
      },
    );
    let total = 1;
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(
        async () => new Response(JSON.stringify({ items: [], total })),
      );
    renderShell(
      <Routes>
        <Route path="/" element={<div>Library page</div>} />
      </Routes>,
    );
    const inboxCalls = () =>
      fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("status=unsorted"),
      ).length;
    expect(
      (await screen.findAllByLabelText("1 waiting in the Inbox")).length,
    ).toBeGreaterThan(0);
    expect(inboxCalls()).toBe(1);

    // A job still running changes nothing in the Inbox yet.
    act(() => sources[0]?.emit("running"));
    expect(inboxCalls()).toBe(1);

    total = 3;
    act(() => sources[0]?.emit("succeeded"));
    expect(
      (await screen.findAllByLabelText("3 waiting in the Inbox")).length,
    ).toBeGreaterThan(0);
    expect(inboxCalls()).toBe(2);
    vi.unstubAllGlobals();
  });
});
