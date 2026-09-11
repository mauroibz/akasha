import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/AppShell";
import { NotFoundPage } from "@/pages/NotFoundPage";

function renderShell(routes: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <AppShell>{routes}</AppShell>
    </MemoryRouter>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("AppShell", () => {
  it("renders Library, Add, Data, and Shelves navigation links", () => {
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
    for (const label of ["Library", "Add", "Data", "Shelves"]) {
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
    const libraryLinks = screen.getAllByRole("link", { name: /library/i });
    const activeLibrary = libraryLinks.find((l) =>
      l.hasAttribute("aria-current"),
    );
    expect(activeLibrary).toBeDefined();
    const addLinks = screen.getAllByRole("link", { name: /^add$/i });
    for (const link of addLinks) {
      expect(link.hasAttribute("aria-current")).toBe(false);
    }
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
      </MemoryRouter>,
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
            <Route path="/" element={<h1>Own library</h1>} />
            <Route
              path="/books/7"
              element={<div role="dialog">Edit entry</div>}
            />
          </Routes>
        </AppShell>
      </MemoryRouter>,
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
});
