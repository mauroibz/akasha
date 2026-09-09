import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthUser } from "@/api/auth";
import { PeoplePage } from "./PeoplePage";

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
  entry_count: 3,
  shelf_count: 1,
};

function renderPage(user: AuthUser = admin) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PeoplePage user={user} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("PeoplePage", () => {
  it("lists people, creates one, and makes deletion an explicit decision", async () => {
    const users = [{ ...admin, entry_count: 12, shelf_count: 4 }, bruno];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/users" && (!init?.method || init.method === "GET")) {
          return new Response(JSON.stringify(users), { status: 200 });
        }
        if (url === "/api/users" && init?.method === "POST") {
          return new Response(JSON.stringify({ ...bruno, id: 3 }), {
            status: 201,
          });
        }
        if (url === "/api/users/2" && init?.method === "DELETE") {
          return new Response(null, { status: 204 });
        }
        if (url === "/api/users/2" && init?.method === "PATCH") {
          return new Response(JSON.stringify({ ...bruno, is_admin: true }), {
            status: 200,
          });
        }
        throw new Error(`Unhandled ${init?.method ?? "GET"} ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    const user = userEvent.setup();

    expect(
      await screen.findByText("@bruno · 3 entries · 1 shelves"),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Username"), "elena");
    await user.type(screen.getAllByLabelText("Display name")[0], "Elena");
    await user.type(
      screen.getByLabelText("Initial password"),
      "a private password",
    );
    await user.click(screen.getByRole("button", { name: "Create person" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/users",
        expect.objectContaining({ method: "POST" }),
      ),
    );

    await user.click(screen.getAllByLabelText("Administrator")[2]);
    await user.click(
      screen.getAllByRole("button", { name: "Save changes" })[1],
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/users/2",
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining('"is_admin":true'),
        }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "Delete bruno" }));
    const confirm = screen.getByRole("button", { name: "Confirm deletion" });
    expect(confirm).toBeDisabled();
    expect(screen.getByText(/They own 3 entries and 1 shelves/)).toBeVisible();
    await user.click(
      screen.getByLabelText("Delete their entries, shelves and import history"),
    );
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/users/2",
        expect.objectContaining({
          method: "DELETE",
          body: JSON.stringify({ action: "delete" }),
        }),
      ),
    );
  });

  it("shows a non-admin only their password settings", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage(bruno);

    expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Change password" }),
    ).toBeVisible();
    expect(screen.queryByRole("heading", { name: "People" })).toBeNull();
    expect(screen.queryByText("Add a person")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
