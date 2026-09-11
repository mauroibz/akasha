import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

const admin = {
  id: 1,
  username: "mauro",
  display_name: "Mauro",
  is_admin: true,
};

function renderPage(onAuthenticated = vi.fn()) {
  return {
    onAuthenticated,
    ...render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/login",
            state: { returnTo: "/shelves/favorites" },
          },
        ]}
      >
        <Routes>
          <Route
            path="/login"
            element={<LoginPage onAuthenticated={onAuthenticated} />}
          />
          <Route path="/shelves/favorites" element={<h1>Favorites shelf</h1>} />
        </Routes>
      </MemoryRouter>,
    ),
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

describe("LoginPage", () => {
  it("submits credentials and returns to the address that asked", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(admin), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { onAuthenticated } = renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Username"), "mauro");
    await user.type(screen.getByLabelText("Password"), "correct horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { name: "Favorites shelf" }),
    ).toBeVisible();
    expect(onAuthenticated).toHaveBeenCalledWith(admin);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/login", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username: "mauro", password: "correct horse" }),
    });
    expect(localStorage).toHaveLength(0);
    expect(sessionStorage).toHaveLength(0);
  });

  it("uses the password-manager form contract", () => {
    renderPage();
    const username = screen.getByLabelText("Username");
    const password = screen.getByLabelText("Password");
    const form = screen
      .getByRole("button", { name: "Sign in" })
      .closest("form");

    expect(form).toHaveAttribute("action", "/api/auth/login");
    expect(form).toHaveAttribute("method", "post");
    expect(username).toHaveAttribute("name", "username");
    expect(username).toHaveAttribute("autocomplete", "username");
    expect(password).toHaveAttribute("name", "password");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "current-password");
  });

  it("keeps the username, clears and focuses the password after refusal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                code: "unauthenticated",
                message: "Authentication is required",
                details: {},
              },
            }),
            { status: 401 },
          ),
      ),
    );
    renderPage();
    const user = userEvent.setup();
    const username = screen.getByLabelText("Username");
    const password = screen.getByLabelText("Password");

    await user.type(username, "mauro");
    await user.type(password, "wrong password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Username or password is incorrect",
    );
    expect(username).toHaveValue("mauro");
    expect(password).toHaveValue("");
    await waitFor(() => expect(password).toHaveFocus());
    expect(
      screen.queryByRole("heading", { name: "Favorites shelf" }),
    ).toBeNull();
  });
});
