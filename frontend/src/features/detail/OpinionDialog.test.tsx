import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LibraryEntry } from "@/api/library";
import { localDay } from "@/features/progress/outline";

import { OpinionDialog } from "./OpinionDialog";

const types = [
  {
    id: "book",
    label: "Book",
    plural_label: "Books",
    fields: [],
    statuses: [
      { value: "read", label: "Read", choosable: true, finished: true },
      {
        value: "reading",
        label: "Reading",
        choosable: true,
        in_progress: true,
      },
      { value: "to_read", label: "To read", choosable: true, planned: true },
    ],
    default_status: "to_read",
    entry_fields: ["date_started", "date_finished", "reread_count"],
    entry_field_labels: {},
    progress: null,
    formats: [],
    entry_panel_label: "Your reading data",
    chooses_covers: false,
  },
];

function entry(changes: Partial<LibraryEntry> = {}): LibraryEntry {
  return {
    id: 7,
    item_id: 9,
    status: "reading",
    score: null,
    notes: null,
    date_added: "2026-07-22T00:00:00Z",
    date_started: "2026-11-01",
    date_finished: null,
    reread_count: 0,
    score_provisional: false,
    suggested_status: null,
    item: {
      id: 9,
      type: "book",
      title: "Rayuela",
      subtitle: null,
      year: 1963,
      creator: "Cortázar, Julio",
      cover_path: null,
      cover_url: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    shelves: [],
    formats: [],
    ...changes,
  } as unknown as LibraryEntry;
}

function renderDialog(value: LibraryEntry) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(types))),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <OpinionDialog
        open
        onOpenChange={() => {}}
        entry={value}
        onSave={async () => {}}
      />
    </QueryClientProvider>,
  );
}

async function chooseRead() {
  const user = userEvent.setup();
  const finished = await screen.findByLabelText("Finished");
  await user.click(screen.getByRole("combobox", { name: /Status/ }));
  await user.click(await screen.findByRole("option", { name: /^Read(?!ing)/ }));
  return finished as HTMLInputElement;
}

afterEach(() => vi.unstubAllGlobals());

describe("OpinionDialog (DEC-192)", () => {
  it("fills today when a finished status is chosen and no date is set", async () => {
    renderDialog(entry());
    const finished = await chooseRead();
    await waitFor(() => expect(finished.value).toBe(localDay(new Date())));
  });

  it("keeps a finished date already there", async () => {
    renderDialog(entry({ date_finished: "2026-03-04" }));
    const finished = await chooseRead();
    expect(finished.value).toBe("2026-03-04");
  });
});
