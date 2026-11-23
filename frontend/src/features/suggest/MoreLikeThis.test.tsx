import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { JobEvent } from "@/api/events";
import type { ItemType } from "@/api/library";
import type { Suggestion, SuggestionRound } from "@/api/suggestions";
import {
  JobEventsContext,
  type JobListener,
} from "@/features/activity/jobEvents";
import { SuggestedModule } from "@/features/home/SuggestedModule";
import { renderWithRouter, types as homeTypes } from "@/features/home/testHome";

import { MoreLikeThis } from "./MoreLikeThis";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const ATTRIBUTION =
  "This product uses the TMDB API but is not endorsed or certified by TMDB.";

function withSource(configured: boolean): ItemType[] {
  return homeTypes.map((type) =>
    type.id === "movie"
      ? {
          ...type,
          recommendation: {
            sources: [
              {
                name: "tmdb",
                label: "TMDB",
                configured,
                hint: configured
                  ? null
                  : "TMDB is not configured. Set TMDB_READ_TOKEN in the server's environment and restart.",
              },
            ],
            attribution: { tmdb: ATTRIBUTION },
          },
        }
      : type,
  );
}

function suggestion(
  id: number,
  title: string,
  values: Partial<Suggestion> = {},
): Suggestion {
  return {
    id,
    round_id: 7,
    item_type: "movie",
    source: "tmdb",
    title,
    year: 1961,
    creator: null,
    external_ids: { tmdb: String(id) },
    reason: { signal: "tmdb", text: "TMDB: often watched together" },
    source_score: null,
    display: {},
    enrichment: "pending",
    item_id: null,
    entry_id: null,
    cover_url: null,
    seed: { entry_id: 3, title: "Seven Samurai" },
    answer: null,
    answered_at: null,
    created_at: "2026-11-23T10:00:00Z",
    ...values,
  } as Suggestion;
}

function round(
  status: SuggestionRound["status"],
  suggestions: Suggestion[],
): SuggestionRound {
  return {
    id: 7,
    item_type: "movie",
    seed_entry_id: 3,
    source: "tmdb",
    status,
    error: null,
    created_at: "2026-11-23T10:00:00Z",
    finished_at: null,
    suggestions,
  } as SuggestionRound;
}

const seed = { entryId: 3, title: "Seven Samurai", type: "movie" };

describe("More like this", () => {
  it("is not offered for a library nothing suggests", () => {
    renderWithRouter(
      <MoreLikeThis
        seed={{ ...seed, type: "book" }}
        types={withSource(true)}
      />,
    );
    expect(screen.queryByRole("button", { name: /More like/ })).toBeNull();
  });

  it("explains a source that is not configured and asks nothing", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    renderWithRouter(<MoreLikeThis seed={seed} types={withSource(false)} />);
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "More like Seven Samurai" }));
    const sheet = screen.getByRole("dialog", {
      name: "More like Seven Samurai",
    });
    expect(within(sheet).getByText(/Set TMDB_READ_TOKEN/)).toBeVisible();
    expect(within(sheet).queryByRole("button", { name: "Refresh" })).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("fills in as the round's job reports, and answers each pick", async () => {
    const listeners = new Set<JobListener>();
    let current = round("queued", []);
    const calls: Array<{ method: string; url: string; body?: unknown }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({
          method,
          url,
          body: init?.body ? JSON.parse(String(init.body)) : undefined,
        });
        if (method === "PATCH") {
          const id = Number(url.split("/").pop());
          const answered = current.suggestions.find((row) => row.id === id)!;
          return new Response(
            JSON.stringify({ ...answered, answer: "want", entry_id: 90 }),
          );
        }
        if (method === "POST" && url.includes("/enrich"))
          return new Response(
            JSON.stringify({
              suggestion: current.suggestions[2],
              job_id: "job-2",
            }),
            { status: 202 },
          );
        return new Response(JSON.stringify(current), {
          status: method === "POST" ? 202 : 200,
        });
      }),
    );
    renderWithRouter(
      <JobEventsContext.Provider
        value={{
          jobs: [],
          subscribe: (listener) => {
            listeners.add(listener);
            return () => listeners.delete(listener);
          },
        }}
      >
        <MoreLikeThis seed={seed} types={withSource(true)} />
      </JobEventsContext.Provider>,
    );
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "More like Seven Samurai" }),
    );
    const sheet = screen.getByRole("dialog", {
      name: "More like Seven Samurai",
    });
    await waitFor(() =>
      expect(within(sheet).getByText("Asking TMDB…")).toBeVisible(),
    );
    expect(calls[0]).toMatchObject({
      method: "POST",
      url: "/api/entries/3/more-like-this",
    });
    expect(within(sheet).getByText(ATTRIBUTION)).toBeVisible();

    current = round("done", [
      suggestion(11, "Yojimbo", {
        enrichment: "enriched",
        item_id: 40,
        cover_url: "/api/items/40/cover?v=1",
      }),
      suggestion(12, "Kagemusha", { enrichment: "enriched", item_id: 41 }),
      suggestion(13, "Rashomon"),
      suggestion(14, "Invented", { enrichment: "unresolved" }),
    ]);
    const event: JobEvent = {
      id: "job-1",
      batch_id: null,
      kind: "recommend",
      state: "succeeded",
      progress: { round_id: 7, status: "done" },
      error: null,
      error_code: null,
      attempts: 1,
      updated_at: "2026-11-23T10:00:01Z",
    };
    act(() => {
      for (const listener of listeners) listener(event);
    });
    const list = await within(sheet).findByRole("list", {
      name: "Suggestions",
    });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(
      within(sheet).getByText(
        /3 picked by TMDB in one request · 2 found so far/,
      ),
    ).toBeVisible();
    expect(within(list).queryByText("Invented")).toBeNull();

    await user.click(
      within(list).getByRole("button", { name: "Look up Rashomon (1961)" }),
    );
    await waitFor(() =>
      expect(
        calls.some((call) => call.url === "/api/suggestions/13/enrich"),
      ).toBe(true),
    );
    expect(within(list).getByText("Looking it up…")).toBeVisible();

    await user.click(
      within(list).getByRole("button", { name: "Want Yojimbo (1961)" }),
    );
    await waitFor(() =>
      expect(
        within(list).getByRole("link", { name: "On your list" }),
      ).toHaveAttribute("href", "/books/90"),
    );
    expect(calls.find((call) => call.method === "PATCH")).toMatchObject({
      url: "/api/suggestions/11",
      body: { answer: "want" },
    });
  });
});

describe("Home's More like this", () => {
  it("shows found picks with TMDB's line, and wants one in a tap", async () => {
    const bodies: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
        if (init?.method === "PATCH")
          bodies.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify(suggestion(11, "Yojimbo")));
      }),
    );
    const picks = [
      suggestion(11, "Yojimbo", { enrichment: "enriched", item_id: 40 }),
      suggestion(12, "Kagemusha", { enrichment: "enriched", item_id: 41 }),
      suggestion(13, "Ran", { enrichment: "enriched", item_id: 42 }),
    ];
    renderWithRouter(
      <SuggestedModule suggestions={picks} types={withSource(true)} size="S" />,
    );
    const module = screen.getByRole("region", { name: "More like this" });
    // S shows two.
    expect(within(module).getAllByRole("listitem")).toHaveLength(2);
    expect(within(module).getAllByText("Like Seven Samurai")).toHaveLength(2);
    expect(within(module).getByText(ATTRIBUTION)).toBeVisible();
    await userEvent
      .setup()
      .click(
        within(module).getByRole("button", { name: "Want Yojimbo (1961)" }),
      );
    await waitFor(() => expect(bodies).toEqual([{ answer: "want" }]));
  });
});
