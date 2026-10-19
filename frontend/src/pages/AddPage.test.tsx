import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { takeHandedFiles } from "@/features/import/handoff";
import { findToast } from "@/test/toast";
import { AddPage } from "./AddPage";

/**
 * `/add` after Sprint 029: manual entry, and nothing else.
 *
 * Searching, the results list, the provider-health notice, the near-match
 * confirmation and the confirm form's own behaviour all moved. They are not gone:
 * the flow from `/` is tested against the functionality inventory in
 * `HomePage.test.tsx`, and the form itself in `features/add/AddForm.test.tsx`.
 * What is left here is what this route is now for.
 */

function renderPage(initialEntry = "/add") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/add" element={<AddPage />} />
          <Route path="/books/:id" element={<h1>Book detail</h1>} />
          <Route path="/" element={<h1>Library page</h1>} />
          <Route path="/import" element={<ImportProbe />} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

/** Where a drop lands: the import screen, holding the files it was handed. */
function ImportProbe() {
  const location = useLocation();
  const files = takeHandedFiles("epub") ?? [];
  return (
    <h1>
      Import {location.search} {files.map((file) => file.name).join(",")}
    </h1>
  );
}

/** One connector that declares itself droppable on Add, one that does not. */
const importers = [
  {
    id: "goodreads",
    label: "Goodreads",
    item_types: ["book"],
    attachment_max_bytes: 25 * 1024 * 1024,
    input: {
      kind: "upload",
      label: "Goodreads CSV",
      field: "file",
      accept: ".csv",
      placeholder: null,
      help: null,
      guide: [],
      empty_state: null,
      help_url: null,
      browsable: false,
      incremental: false,
      accepts_files: false,
      max_bytes: null,
      max_files: null,
      quick_add: false,
      alternates: [],
    },
  },
  {
    id: "epub",
    label: "Ebook files",
    item_types: ["book"],
    attachment_max_bytes: 25 * 1024 * 1024,
    input: {
      kind: "export",
      label: "EPUB files",
      field: "files",
      accept: ".epub",
      placeholder: null,
      help: "Drop EPUB files and each one becomes a book.",
      guide: [],
      empty_state: "Drop .epub files here.",
      help_url: null,
      browsable: false,
      incremental: false,
      accepts_files: true,
      max_bytes: null,
      max_files: 100,
      quick_add: true,
      alternates: [],
    },
  },
];

/** The two domains `GET /api/item-types` publishes (DEC-052 seam 3). */
const itemTypes = [
  {
    id: "book",
    label: "Book",
    fields: [
      {
        name: "creators",
        label: "Creators",
        type: "text",
        multiplicity: "many",
      },
      {
        name: "publisher",
        label: "Publisher",
        type: "text",
        multiplicity: "one",
      },
    ],
    statuses: [
      { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
      { value: "read", label: "Read", choosable: true, hotkey: "r" },
    ],
    default_status: "read",
    entry_fields: ["date_started", "date_finished", "reread_count"],
    formats: [],
    entry_panel_label: "Your reading data",
    chooses_covers: true,
  },
  {
    id: "album",
    label: "Album",
    fields: [
      {
        name: "creators",
        label: "Artists",
        type: "text",
        multiplicity: "many",
      },
      { name: "label", label: "Label", type: "text", multiplicity: "one" },
    ],
    statuses: [
      { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
      { value: "owned", label: "Owned", choosable: true, hotkey: "o" },
    ],
    default_status: "owned",
    entry_fields: [],
    formats: [],
    entry_panel_label: "Your copy",
    chooses_covers: false,
  },
];

function stubApi(onCreate?: () => Response) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/item-types")
        return new Response(JSON.stringify(itemTypes));
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/importers")
        return new Response(JSON.stringify(importers));
      if (url === "/api/entries" && init?.method === "POST")
        return (
          onCreate?.() ??
          new Response(
            JSON.stringify({
              entry: { id: 11 },
              already_exists: false,
              near_matches: [],
            }),
            { status: 201 },
          )
        );
      return new Response(JSON.stringify({ providers: [], degraded: false }));
    });
}

describe("AddPage", () => {
  it("is a working deep link straight to the manual form", async () => {
    stubApi();
    renderPage();

    // AC6. No search, no results list, no step before the form.
    expect(
      await screen.findByRole("heading", { name: /enter by hand/i }),
    ).toBeVisible();
    expect(screen.getByLabelText(/^title$/i)).toBeVisible();
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /enter manually/i }),
    ).toBeNull();
  });

  it("puts the cursor in the title field, which is the only thing to do here", async () => {
    stubApi();
    renderPage();

    // Inventory row 9: the manual path's first focus.
    await waitFor(() =>
      expect(screen.getByLabelText(/^title$/i)).toHaveFocus(),
    );
  });

  it("chooses a domain and sends that domain's declared manual fields", async () => {
    const request = stubApi();
    renderPage();

    const domain = await screen.findByRole("combobox", { name: /domain/i });
    await userEvent.click(domain);
    await userEvent.click(screen.getByRole("option", { name: "Album" }));
    expect(screen.getByLabelText(/artists, comma separated/i)).toBeVisible();
    expect(screen.getByLabelText(/^label$/i)).toBeVisible();
    expect(screen.queryByLabelText(/^publisher$/i)).toBeNull();

    await userEvent.type(screen.getByLabelText(/^title$/i), "Ágætis byrjun");
    await userEvent.type(
      screen.getByLabelText(/artists, comma separated/i),
      "Sigur Rós",
    );
    await userEvent.type(screen.getByLabelText(/^label$/i), "FatCat Records");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );

    const write = request.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
      manual: {
        item_type: "album",
        title: "Ágætis byrjun",
        metadata: {
          creators: ["Sigur Rós"],
          label: "FatCat Records",
        },
      },
      status: "owned",
    });
  });

  it("submits a manual entry once and announces exact duplicates", async () => {
    const request = stubApi(
      () =>
        new Response(
          JSON.stringify({
            entry: { id: 7 },
            already_exists: true,
            near_matches: [],
          }),
          { status: 200 },
        ),
    );
    renderPage();

    await userEvent.type(await screen.findByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    await screen.findByRole("heading", { name: /book detail/i });
    // Inventory row 10: a 200 rather than a 201, and exactly one write.
    expect(
      request.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
    expect(await findToast("Already in your library")).toBeInTheDocument();
  });

  it("confirms a successful add on the visible toast surface", async () => {
    stubApi();
    renderPage();

    await userEvent.type(await screen.findByLabelText(/^title$/i), "Rayuela");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    await screen.findByRole("heading", { name: /library page/i });
    // The domain's own label, not the word "Book" typed into this file.
    expect(await findToast("Book added")).toBeInTheDocument();
  });

  it("refuses an empty title and keeps everything else typed", async () => {
    const request = stubApi();
    renderPage();

    await userEvent.type(
      await screen.findByLabelText(/^creators, comma separated$/i),
      "Julio Cortázar",
    );
    await userEvent.type(screen.getByLabelText(/^year$/i), "1963");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );

    // The field error is announced and tied to the control that caused it.
    const title = screen.getByLabelText(/^title$/i);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /title is required/i,
    );
    expect(title).toHaveAttribute("aria-invalid", "true");
    expect(title).toHaveAttribute(
      "aria-describedby",
      screen.getByRole("alert").id,
    );
    // Nothing was sent, and nothing typed was discarded.
    expect(
      request.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(0);
    expect(screen.getByLabelText(/^creators, comma separated$/i)).toHaveValue(
      "Julio Cortázar",
    );
    expect(screen.getByLabelText(/^year$/i)).toHaveValue(1963);
  });

  it("refuses an invalid declared number without discarding the rest of the form", async () => {
    stubApi();
    renderPage();

    await userEvent.type(await screen.findByLabelText(/^title$/i), "Rayuela");
    await userEvent.type(screen.getByLabelText(/^year$/i), "10000");
    await userEvent.click(
      screen.getByRole("button", { name: /add to library/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/year/i);
    expect(screen.getByLabelText(/^title$/i)).toHaveValue("Rayuela");
    expect(screen.getByLabelText(/^year$/i)).toHaveValue(10000);
  });

  it("offers a drop zone for each connector that declares quick add, and only those", async () => {
    stubApi();
    renderPage();

    expect(await screen.findByLabelText("EPUB files")).toHaveAttribute(
      "multiple",
    );
    expect(screen.getByText("Drop .epub files here.")).toBeVisible();
    expect(screen.queryByLabelText("Goodreads CSV")).toBeNull();
    // Manual entry is still the page's first focus.
    await waitFor(() =>
      expect(screen.getByLabelText(/^title$/i)).toHaveFocus(),
    );
  });

  it("drops three files and opens the import screen on that connector, holding them", async () => {
    stubApi();
    renderPage();

    const zone = await screen.findByTestId("epub-export-drop-zone");
    const files = ["a.epub", "b.epub", "c.epub"].map(
      (name) => new File([name], name),
    );
    fireEvent.drop(zone, { dataTransfer: { files } });

    expect(
      await screen.findByRole("heading", {
        name: "Import ?tab=epub a.epub,b.epub,c.epub",
      }),
    ).toBeVisible();
  });
});
