import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SuggestedShelves } from "./SuggestedShelves";

const member = (id: number, title: string) => ({
  entry_id: id,
  title,
  year: 1970,
  score: 9,
  cover_url: null,
});

afterEach(() => vi.restoreAllMocks());

function renderIt() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <SuggestedShelves />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SuggestedShelves (Sprint 119)", () => {
  it("offers each shelf the library implies, made in one tap or let go for good", async () => {
    let offered = [
      {
        key: "creator:ursula k le guin",
        kind: "creator",
        name: "Ursula K. Le Guin",
        reason: "3 by Ursula K. Le Guin",
        members: [
          member(1, "The Dispossessed"),
          member(2, "The Left Hand of Darkness"),
          member(3, "The Lathe of Heaven"),
        ],
      },
      {
        key: "work:dune",
        kind: "work",
        name: "Dune",
        reason: "Dune in 2 libraries",
        members: [member(4, "Dune"), member(5, "Dune: Part One")],
      },
    ];
    const posts: Array<{ url: string; body: unknown }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as { key: string };
        posts.push({ url, body });
        offered = offered.filter((row) => row.key !== body.key);
        return url.endsWith("/accept")
          ? new Response(
              JSON.stringify({
                id: 9,
                name: "Ursula K. Le Guin",
                slug: "ursula-k-le-guin",
              }),
              { status: 201 },
            )
          : new Response(null, { status: 204 });
      }
      if (url === "/api/shelves/suggestions")
        return new Response(JSON.stringify(offered));
      return new Response("[]");
    });
    renderIt();
    const user = userEvent.setup();
    const section = await screen.findByRole("region", {
      name: "Suggested shelves",
    });
    const guin = within(section).getByRole("group", {
      name: "Ursula K. Le Guin",
    });
    expect(guin).toHaveTextContent("3 by Ursula K. Le Guin");
    await user.click(
      within(guin).getByRole("button", { name: "Make this a shelf" }),
    );
    await waitFor(() =>
      expect(
        within(section).queryByRole("group", { name: "Ursula K. Le Guin" }),
      ).toBeNull(),
    );
    await user.click(
      within(within(section).getByRole("group", { name: "Dune" })).getByRole(
        "button",
        {
          name: "Not useful",
        },
      ),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "Suggested shelves" }),
      ).toBeNull(),
    );
    expect(posts).toEqual([
      {
        url: "/api/shelves/suggestions/accept",
        body: { key: "creator:ursula k le guin" },
      },
      { url: "/api/shelves/suggestions/dismiss", body: { key: "work:dune" } },
    ]);
  });
});
