import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountSection } from "./AccountSection";

function renderSection(onSignedOut = vi.fn()) {
  return {
    onSignedOut,
    ...render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <AccountSection onPasswordChanged={vi.fn()} onSignedOut={onSignedOut} />
      </QueryClientProvider>,
    ),
  };
}

afterEach(() => vi.restoreAllMocks());

describe("AccountSection", () => {
  it("shows recognizable sessions and revokes another device", async () => {
    const sessions = [
      {
        id: "desktop",
        created_at: "2026-09-01T12:00:00Z",
        last_seen_at: "2026-09-10T12:00:00Z",
        user_agent: "Firefox on Linux",
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
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/auth/sessions" && !init?.method) {
          return new Response(JSON.stringify(sessions), { status: 200 });
        }
        if (
          String(input) === "/api/auth/sessions/phone" &&
          init?.method === "DELETE"
        ) {
          return new Response(null, { status: 204 });
        }
        throw new Error(`Unhandled ${init?.method ?? "GET"} ${String(input)}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    renderSection();
    const user = userEvent.setup();

    expect(await screen.findByText("Firefox on Linux")).toBeVisible();
    expect(screen.getByText("Current session")).toBeVisible();
    expect(screen.getByText("Mobile Safari")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Sign out Mobile Safari" }),
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/auth/sessions/phone", {
        method: "DELETE",
      }),
    );
    await waitFor(() => expect(screen.queryByText("Mobile Safari")).toBeNull());
  });

  it("signs out this device or every device", async () => {
    const sessions = [
      {
        id: "desktop",
        created_at: "2026-09-01T12:00:00Z",
        last_seen_at: "2026-09-10T12:00:00Z",
        user_agent: null,
        current: true,
      },
    ];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/auth/sessions" && !init?.method) {
          return new Response(JSON.stringify(sessions), { status: 200 });
        }
        return new Response(null, { status: 204 });
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const first = renderSection();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Sign out this session" }),
    );
    expect(first.onSignedOut).toHaveBeenCalledOnce();

    first.unmount();
    const second = renderSection();
    await user.click(
      await screen.findByRole("button", { name: "Sign out everywhere" }),
    );
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/sessions", {
      method: "DELETE",
    });
    expect(second.onSignedOut).toHaveBeenCalledOnce();
  });
});
