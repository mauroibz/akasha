import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NowStrip } from "./NowStrip";

const anime = {
  id: "anime",
  label: "Anime",
  progress: {
    label: "Episodes watched",
    unit_label: "episode",
    total_field: "episodes",
  },
  statuses: [],
  fields: [],
};
const watching = {
  id: 5,
  status: "watching",
  progress: 3,
  item: {
    id: 9,
    type: "anime",
    title: "Frieren",
    cover_url: null,
    metadata: { episodes: 28 },
    identifiers: {},
  },
};

afterEach(() => vi.restoreAllMocks());

function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <NowStrip />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("NowStrip", () => {
  it("shows what is under way and advances it by one episode", async () => {
    const patches: unknown[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        patches.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify({ ...watching, progress: 4 }));
      }
      if (url === "/api/now") return new Response(JSON.stringify([watching]));
      if (url.startsWith("/api/item-types"))
        return new Response(JSON.stringify([anime]));
      return new Response("[]");
    });
    mount();
    expect(await screen.findByRole("heading", { name: "Now" })).toBeVisible();
    expect(await screen.findByText("3 / 28 episodes")).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Add 1 episode to Frieren" }),
    );
    expect(await screen.findByText("4 / 28 episodes")).toBeVisible();
    await waitFor(() => expect(patches).toEqual([{ progress: 4 }]));
  });

  it("says nothing when nothing is under way", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response("[]"),
    );
    mount();
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Now" })).toBeNull(),
    );
  });

  it("finishes something from the strip, in the finish sheet (Sprint 123)", async () => {
    const patches: unknown[] = [];
    const types = [
      {
        ...anime,
        statuses: [
          { value: "watching", label: "Watching", in_progress: true },
          { value: "completed", label: "Completed", finished: true },
        ],
        entry_fields: ["date_finished"],
        formats: [],
      },
    ];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        patches.push(JSON.parse(String(init.body)));
        return new Response(
          JSON.stringify({ ...watching, status: "completed" }),
        );
      }
      if (url === "/api/now")
        return new Response(
          JSON.stringify([{ ...watching, score: null, formats: [] }]),
        );
      if (url.startsWith("/api/item-types"))
        return new Response(JSON.stringify(types));
      return new Response("[]");
    });
    mount();
    await userEvent.click(
      await screen.findByRole("button", { name: "Finished Frieren" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Finish" }),
    );
    await waitFor(() =>
      expect(patches[0]).toMatchObject({ status: "completed" }),
    );
  });
});
