import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ItemType, LibraryEntry } from "@/api/library";
import { localDay } from "@/features/progress/outline";

import { FinishDialog } from "./FinishDialog";

const book = {
  id: "book",
  label: "Book",
  fields: [],
  statuses: [
    { value: "reading", label: "Reading", in_progress: true },
    { value: "read", label: "Read", finished: true },
  ],
  default_status: "read",
  entry_fields: ["date_started", "date_finished", "reread_count"],
  formats: [
    { value: "physical", label: "Physical" },
    { value: "digital", label: "Digital" },
  ],
  entry_panel_label: "Your reading data",
} as unknown as ItemType;

const entry = (changes: Partial<LibraryEntry> = {}) =>
  ({
    id: 4,
    status: "reading",
    score: null,
    reread_count: 0,
    formats: [],
    item: { id: 4, type: "book", title: "Rayuela" },
    ...changes,
  }) as unknown as LibraryEntry;

function stub() {
  const bodies: Record<string, unknown>[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
    const body = JSON.parse(String(init?.body ?? "{}"));
    bodies.push(body);
    return new Response(JSON.stringify({ ...entry(), ...body }));
  });
  return bodies;
}

function renderDialog(value: LibraryEntry, onFinished = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FinishDialog
        entry={value}
        types={[book]}
        onClose={() => {}}
        onFinished={onFinished}
      />
    </QueryClientProvider>,
  );
  return onFinished;
}

afterEach(() => vi.restoreAllMocks());

describe("FinishDialog (Sprint 123)", () => {
  it("finishes today in one tap, asking nothing it was not told", async () => {
    const bodies = stub();
    const done = renderDialog(entry());
    expect(
      screen.getByRole("heading", { name: "You finished Rayuela" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Today" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await userEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(bodies[0]).toEqual({
      status: "read",
      date_finished: localDay(new Date()),
    });
    expect(done).toHaveBeenCalled();
  });

  it("takes another day, a score and a format", async () => {
    const bodies = stub();
    renderDialog(entry());
    await userEvent.click(screen.getByRole("button", { name: "Another day" }));
    const day = screen.getByLabelText("The day you finished");
    await userEvent.clear(day);
    await userEvent.type(day, "2026-09-30");
    await userEvent.click(screen.getByRole("button", { name: "Score 9" }));
    await userEvent.click(screen.getByRole("button", { name: "Digital" }));
    await userEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(bodies[0]).toEqual({
      status: "read",
      date_finished: "2026-09-30",
      score: 9,
      formats: ["digital"],
    });
  });

  it("asks whether a reread's score still holds, and keeping it is history", async () => {
    const bodies = stub();
    renderDialog(entry({ score: 8, reread_count: 1, formats: ["physical"] }));
    expect(screen.getByText("Still an 8?")).toBeVisible();
    // A format already known is not asked again.
    expect(screen.queryByRole("button", { name: "Digital" })).toBeNull();
    await userEvent.type(
      screen.getByRole("textbox", { name: /Why, in a line/ }),
      "Better the second time",
    );
    await userEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(bodies[0]).toEqual({
      status: "read",
      date_finished: localDay(new Date()),
      score: 8,
      score_reason: "reread",
      score_note: "Better the second time",
    });
  });
});
