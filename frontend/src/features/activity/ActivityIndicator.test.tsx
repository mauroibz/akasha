import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { JobEvent } from "@/api/events";

import { ActivityIndicator } from "./ActivityIndicator";
import { JobEventsProvider } from "./JobEvents";

class FakeEventSource {
  static last: FakeEventSource | null = null;
  listeners = new Map<string, (message: MessageEvent<string>) => void>();
  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }
  addEventListener(type: string, listener: (m: MessageEvent<string>) => void) {
    this.listeners.set(type, listener);
  }
  removeEventListener() {}
  close() {}
  emit(job: Partial<JobEvent>) {
    const event: JobEvent = {
      id: "j1",
      batch_id: null,
      kind: "search_import_rows",
      state: "running",
      progress: {},
      error: null,
      error_code: null,
      attempts: 0,
      updated_at: new Date().toISOString(),
      ...job,
    };
    this.listeners.get("job")?.({
      data: JSON.stringify(event),
    } as MessageEvent<string>);
  }
}

afterEach(() => vi.unstubAllGlobals());

describe("ActivityIndicator", () => {
  it("breathes while a job runs, lists it, and offers Retry once it fails", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    render(
      <JobEventsProvider>
        <ActivityIndicator />
      </JobEventsProvider>,
    );
    const button = screen.getByTestId("activity-indicator");
    expect(button).toHaveAccessibleName("Background work: nothing running");
    expect(FakeEventSource.last?.url).toBe("/api/events");

    act(() =>
      FakeEventSource.last?.emit({ progress: { searched: 12, total: 220 } }),
    );
    expect(button).toHaveAccessibleName("Background work: 1 running");
    expect(button.querySelector("[data-breathing]")).not.toBeNull();

    await userEvent.click(button);
    expect(screen.getByText("Matching import rows")).toBeInTheDocument();
    expect(screen.getByText("12 of 220 rows")).toBeInTheDocument();

    act(() =>
      FakeEventSource.last?.emit({
        state: "failed",
        error: "MusicBrainz could not be reached",
        updated_at: new Date(Date.now() + 1000).toISOString(),
      }),
    );
    expect(button).toHaveAccessibleName("Background work: nothing running");
    expect(button.querySelector("[data-breathing]")).toBeNull();
    expect(
      screen.getByText("MusicBrainz could not be reached"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("shows one batch's jobs as one row with how far it has got", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    render(
      <JobEventsProvider>
        <ActivityIndicator />
      </JobEventsProvider>,
    );
    act(() => {
      for (const [index, state] of (
        ["succeeded", "running", "queued"] as const
      ).entries())
        FakeEventSource.last?.emit({
          id: `e${index}`,
          batch_id: "b1",
          kind: "enrich_item",
          state,
        });
    });
    await userEvent.click(screen.getByTestId("activity-indicator"));
    expect(screen.getAllByText("Filling in details")).toHaveLength(1);
    expect(screen.getByText("1 of 3 done")).toBeInTheDocument();
  });
});
