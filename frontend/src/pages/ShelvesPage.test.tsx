import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { findToast } from "@/test/toast";
import { ShelvesPage } from "./ShelvesPage";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ShelvesPage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const shelves = [
  { id: 1, name: "Favorites", slug: "favorites", entry_count: 5 },
  { id: 2, name: "Sci-fi", slug: "sci-fi", entry_count: 3 },
];

describe("ShelvesPage", () => {
  it("lists shelves with entry counts", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/shelves")
        return new Response(JSON.stringify(shelves));
      return new Response("[]");
    });
    renderPage();
    expect(await screen.findByText("Favorites")).toBeVisible();
    // A shelf spans domains and always did, so it counts items rather than
    // naming one domain's noun (Sprint 029 deliverable 6).
    expect(screen.getByText("5 items")).toBeVisible();
    expect(screen.getByText("Sci-fi")).toBeVisible();
    expect(screen.getByText("3 items")).toBeVisible();
  });

  it("creates a shelf and refreshes the list", async () => {
    let created = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (init?.method === "POST" && url === "/api/shelves") {
        created = true;
        return new Response(
          JSON.stringify({ id: 3, name: "New", slug: "new", entry_count: 0 }),
          { status: 201 },
        );
      }
      if (url === "/api/shelves")
        return new Response(
          JSON.stringify(
            created
              ? [
                  ...shelves,
                  { id: 3, name: "New", slug: "new", entry_count: 0 },
                ]
              : shelves,
          ),
        );
      return new Response("[]");
    });
    renderPage();
    await screen.findByText("Favorites");
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/new shelf name/i), "New");
    await user.click(screen.getByRole("button", { name: /create shelf/i }));
    await waitFor(() => expect(screen.getByText("New")).toBeVisible());
  });

  it("renames a shelf", async () => {
    let renamed = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (init?.method === "PATCH" && url.includes("/api/shelves/1")) {
        renamed = true;
        return new Response(
          JSON.stringify({ id: 1, name: "Best", slug: "best", entry_count: 5 }),
        );
      }
      if (url === "/api/shelves")
        return new Response(
          JSON.stringify(
            renamed
              ? [
                  { id: 1, name: "Best", slug: "best", entry_count: 5 },
                  shelves[1],
                ]
              : shelves,
          ),
        );
      return new Response("[]");
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByText("Favorites");
    await user.click(screen.getByRole("button", { name: /rename favorites/i }));
    const input = await screen.findByDisplayValue("Favorites");
    await user.clear(input);
    await user.type(input, "Best");
    await user.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(screen.getByText("Best")).toBeVisible());
    expect(await findToast('Shelf renamed to "Best"')).toBeInTheDocument();
  });

  it("confirms deletion and states the entries are retained", async () => {
    let deleted = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (init?.method === "DELETE" && url.includes("/api/shelves/1")) {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      if (url === "/api/shelves")
        return new Response(
          JSON.stringify(deleted ? shelves.slice(1) : shelves),
        );
      return new Response("[]");
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByText("Favorites");
    await user.click(screen.getByRole("button", { name: /delete favorites/i }));
    // Confirmation dialog states the entries are retained
    expect(screen.getByText(/entries.*retained/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /delete shelf/i }));
    await waitFor(() => expect(deleted).toBe(true));
    expect(screen.queryByText("Favorites")).not.toBeInTheDocument();
    expect(await findToast("Shelf deleted")).toBeInTheDocument();
  });

  it("surfaces duplicate slug errors", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (init?.method === "POST" && String(input) === "/api/shelves")
        return new Response(
          JSON.stringify({
            error: {
              code: "shelf_slug_conflict",
              message: "Shelf name is already in use",
            },
          }),
          { status: 409 },
        );
      if (String(input) === "/api/shelves")
        return new Response(JSON.stringify(shelves));
      return new Response("[]");
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByText("Favorites");
    await user.type(
      screen.getByPlaceholderText(/new shelf name/i),
      "Favorites",
    );
    await user.click(screen.getByRole("button", { name: /create shelf/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /already in use/i,
    );
  });
});
