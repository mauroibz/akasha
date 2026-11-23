import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GoalWidget } from "./GoalWidget";

afterEach(() => vi.restoreAllMocks());

const type = (id: string, label: string, plural: string) => ({
  id,
  label,
  plural_label: plural,
  fields: [],
  statuses: [],
  default_status: "x",
  entry_fields: ["date_started", "date_finished"],
  formats: [],
});
const album = { ...type("album", "Album", "Albums"), entry_fields: [] };

function serve() {
  const puts: Array<{ url: string; body: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PUT") {
        puts.push({ url, body: JSON.parse(String(init.body)) });
        return new Response(JSON.stringify({}));
      }
      if (url.startsWith("/api/item-types"))
        return new Response(
          JSON.stringify([
            type("book", "Book", "Books"),
            album,
            type("anime", "Anime", "Anime"),
          ]),
        );
      if (url.startsWith("/api/media"))
        return new Response(JSON.stringify({ media: [], chosen: true }));
      if (url.startsWith("/api/diary"))
        return new Response(
          JSON.stringify({
            year: new Date().getFullYear(),
            years: [],
            months: [],
          }),
        );
      return new Response("[]");
    }),
  );
  return puts;
}

describe("GoalWidget (Sprint 149, DEC-195)", () => {
  it("lets the person choose which medium the goal is for, among those a goal can count", async () => {
    const puts = serve();
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <GoalWidget />
      </QueryClientProvider>,
    );
    const chooser = await screen.findByRole("radiogroup", {
      name: "A goal for",
    });
    // Albums record no finish, so a goal cannot count them.
    expect(
      within(chooser)
        .getAllByRole("radio")
        .map((radio) => radio.textContent),
    ).toEqual(["Books", "Anime"]);
    await userEvent.click(
      within(chooser).getByRole("radio", { name: "Anime" }),
    );
    expect(await screen.findByText(/finished 0 anime in/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Aim for 12" }));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].url).toBe("/api/goals/anime");
  });
});
