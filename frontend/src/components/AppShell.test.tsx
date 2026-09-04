import { render, screen } from "@testing-library/react";
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
});
