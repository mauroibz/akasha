import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ItemType, LibraryEntry } from "@/api/library";

import { OneQuestion } from "./OneQuestion";

const book = {
  id: "book",
  statuses: [{ value: "read", label: "Read", finished: true }],
  entry_fields: ["date_started", "date_finished", "reread_count"],
  formats: [
    { value: "physical", label: "Physical" },
    { value: "digital", label: "Digital" },
  ],
} as unknown as ItemType;

const entry = (changes: Partial<LibraryEntry> = {}) =>
  ({
    id: 4,
    status: "read",
    date_started: null,
    date_finished: null,
    formats: [],
    location: null,
    unknown_fields: [],
    item: { id: 4, type: "book", title: "Rayuela" },
    ...changes,
  }) as unknown as LibraryEntry;

function stub() {
  const bodies: Record<string, unknown>[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (init?.method === "PATCH") {
      bodies.push(JSON.parse(String(init.body)));
      return new Response(JSON.stringify(entry()));
    }
    if (String(input).startsWith("/api/locations"))
      return new Response(
        JSON.stringify([
          { location: "Living room", count: 4 },
          { location: "Hall", count: 1 },
        ]),
      );
    return new Response("[]");
  });
  return bodies;
}

const mount = (value: LibraryEntry) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <OneQuestion entry={value} types={[book]} />
    </QueryClientProvider>,
  );

afterEach(() => vi.restoreAllMocks());

describe("OneQuestion (Sprint 124)", () => {
  it("asks the most useful gap first and saves a date", async () => {
    const bodies = stub();
    mount(entry());
    expect(screen.getByText("1 of 4")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "When did you finish it?" }),
    ).toBeVisible();
    const day = screen.getByLabelText("Date");
    await userEvent.clear(day);
    await userEvent.type(day, "2019-05-01");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(bodies[0]).toEqual({ date_finished: "2019-05-01" }),
    );
  });

  it("remembers what the owner does not, and skips for now", async () => {
    const bodies = stub();
    mount(entry({ unknown_fields: ["location"] }));
    await userEvent.click(
      screen.getByRole("button", { name: "I don't remember" }),
    );
    await waitFor(() =>
      expect(bodies[0]).toEqual({
        unknown_fields: ["location", "date_finished"],
      }),
    );
    // Skipping asks the next one and writes nothing.
    await userEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(
      screen.getByRole("heading", { name: "How do you have it?" }),
    ).toBeVisible();
    expect(bodies).toHaveLength(1);
  });

  it("a format and a place are one tap", async () => {
    const bodies = stub();
    mount(entry({ date_finished: "2019-05-01" }));
    await userEvent.click(screen.getByRole("button", { name: "Digital" }));
    await waitFor(() => expect(bodies[0]).toEqual({ formats: ["digital"] }));
    await userEvent.click(screen.getByRole("button", { name: "Skip" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Living room" }),
    );
    await waitFor(() => expect(bodies[1]).toEqual({ location: "Living room" }));
  });

  it("draws nothing when there is nothing to ask", () => {
    stub();
    const { container } = mount(
      entry({
        date_finished: "2019-05-01",
        date_started: "2019-04-01",
        formats: ["physical"],
        location: "Hall",
      }),
    );
    expect(container).toBeEmptyDOMElement();
  });
});
