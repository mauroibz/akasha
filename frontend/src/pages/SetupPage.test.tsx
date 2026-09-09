import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SetupPage } from "./SetupPage";

const admin = {
  id: 1,
  username: "mauro",
  display_name: "Mauro",
  is_admin: true,
};

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

describe("SetupPage", () => {
  it("claims the existing library and returns to the requested address", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(admin), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onAuthenticated = vi.fn();
    const user = userEvent.setup();

    render(
      <MemoryRouter
        initialEntries={[
          { pathname: "/setup", state: { returnTo: "/shelves/favorites" } },
        ]}
      >
        <Routes>
          <Route
            path="/setup"
            element={<SetupPage onAuthenticated={onAuthenticated} />}
          />
          <Route path="/shelves/favorites" element={<h1>Favorites shelf</h1>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText(/claims the library already on this install/i),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Username"), "mauro");
    await user.type(screen.getByLabelText("Display name"), "Mauro");
    await user.type(screen.getByLabelText("Password"), "correct horse");
    await user.click(screen.getByRole("button", { name: "Claim library" }));

    expect(
      await screen.findByRole("heading", { name: "Favorites shelf" }),
    ).toBeVisible();
    expect(onAuthenticated).toHaveBeenCalledWith(admin);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/setup", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username: "mauro",
        display_name: "Mauro",
        password: "correct horse",
      }),
    });
    expect(localStorage).toHaveLength(0);
    expect(sessionStorage).toHaveLength(0);
  });

  it("uses new-password autocomplete and named fields", () => {
    render(
      <MemoryRouter>
        <SetupPage onAuthenticated={vi.fn()} />
      </MemoryRouter>,
    );

    const form = screen
      .getByRole("button", { name: "Claim library" })
      .closest("form");
    expect(form).toHaveAttribute("action", "/api/auth/setup");
    expect(form).toHaveAttribute("method", "post");
    expect(screen.getByLabelText("Username")).toHaveAttribute(
      "name",
      "username",
    );
    expect(screen.getByLabelText("Display name")).toHaveAttribute(
      "name",
      "display_name",
    );
    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("name", "password");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "new-password");
  });
});
