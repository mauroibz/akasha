import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { JobEventsProvider } from "@/features/activity/JobEvents";

import { Arrivals } from "./Arrivals";

class FakeEventSource {
  static last: FakeEventSource | null = null;
  listener: ((message: MessageEvent<string>) => void) | null = null;
  constructor() {
    FakeEventSource.last = this;
  }
  addEventListener(_: string, listener: (m: MessageEvent<string>) => void) {
    this.listener = listener;
  }
  removeEventListener() {}
  close() {}
  finish(id: string) {
    this.listener?.({
      data: JSON.stringify({
        id,
        batch_id: "b1",
        kind: "enrich_item",
        state: "succeeded",
        progress: {},
        error: null,
        error_code: null,
        attempts: 0,
        updated_at: new Date().toISOString(),
      }),
    } as MessageEvent<string>);
  }
}

const entry = (id: number, cover: string | null) => ({
  id,
  status: "unsorted",
  item: {
    id,
    title: `Book ${id}`,
    cover_url: cover,
    metadata: {},
    identifiers: {},
  },
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Arrivals", () => {
  it("counts the batch's enrichment as it finishes and re-reads the covers", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    let reads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      reads += 1;
      return new Response(
        JSON.stringify({
          items: [
            entry(1, reads > 1 ? "/api/items/1/cover" : null),
            entry(2, null),
          ],
          next_cursor: null,
          total: 2,
        }),
      );
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <JobEventsProvider>
          <Arrivals batchId="b1" expected={2} />
        </JobEventsProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/0 of 2 filled in/)).toBeVisible();
    act(() => FakeEventSource.last?.finish("j1"));
    expect(await screen.findByText(/1 of 2 filled in/)).toBeVisible();
    await vi.waitFor(() => expect(reads).toBeGreaterThan(1));
    act(() => FakeEventSource.last?.finish("j2"));
    expect(await screen.findByText("All 2 filled in.")).toBeVisible();
  });
});
