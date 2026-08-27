import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import type { ItemType } from "@/api/library";
import { AddForm } from "./AddForm";
import type { SearchCandidate } from "@/api/add";

/**
 * The confirm step, tested where it lives.
 *
 * These behaviours were AddPage tests until Sprint 029 made the form a component
 * that two screens host. Testing it through either host would assert the host's
 * plumbing as much as the form's, and asserting it twice is how the two copies
 * drift, so it is exercised directly here and each host tests only its own job.
 */

afterEach(() => vi.restoreAllMocks());

const book: ItemType = {
  id: "book",
  label: "Book",
  fields: [],
  statuses: [{ value: "read", label: "Read", choosable: true, hotkey: "r" }],
  default_status: "read",
  entry_fields: ["date_started", "date_finished", "reread_count"],
  formats: [
    { value: "physical", label: "Physical" },
    { value: "digital", label: "Digital" },
  ],
  entry_panel_label: "Your reading data",
} as unknown as ItemType;

const album: ItemType = {
  id: "album",
  label: "Record",
  fields: [],
  statuses: [{ value: "owned", label: "Owned", choosable: true, hotkey: "o" }],
  default_status: "owned",
  entry_fields: [],
  formats: [{ value: "vinyl", label: "Vinyl" }],
  entry_panel_label: "Your copy",
} as unknown as ItemType;

const candidate: SearchCandidate = {
  source: "openlibrary",
  source_id: "OL1M",
  source_refs: [{ source: "openlibrary", source_id: "OL1M" }],
  title: "Rayuela",
  subtitle: null,
  creators: ["Julio Cortázar"],
  credit: "Julio Cortázar",
  year: 1963,
  cover_url: null,
  identifiers: {},
  language: "es",
  metadata: {},
};

function renderForm({
  itemType = "book",
  itemTypes = [book, album],
  manual = false,
  onAdded = vi.fn(),
}: {
  itemType?: string;
  itemTypes?: ItemType[];
  manual?: boolean;
  onAdded?: (id: number, exists: boolean) => void;
} = {}) {
  render(
    <MemoryRouter>
      <AddForm
        itemType={itemType}
        itemTypes={itemTypes}
        candidate={manual ? null : candidate}
        manual={manual}
        onAdded={onAdded}
        onOpenExisting={vi.fn()}
      />
    </MemoryRouter>,
  );
  return userEvent.setup();
}

/** Records every create body so the assertions are about what was actually sent. */
function stubApi(overrides: Record<string, () => Response> = {}) {
  const bodies: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input, init?: RequestInit) => {
      const url = String(input);
      const override = overrides[url + (init?.method ?? "")];
      if (override) return override();
      if (url === "/api/shelves" && init?.method === "POST")
        return new Response(
          JSON.stringify({
            id: 5,
            name: "Ensayo",
            slug: "ensayo",
            entry_count: 0,
          }),
        );
      if (url === "/api/shelves") return new Response("[]");
      if (url === "/api/entries" && init?.method === "POST") {
        bodies.push(String(init.body));
        return new Response(
          JSON.stringify({
            entry: { id: 3, item: { id: 1 } },
            already_exists: false,
            near_matches: [],
          }),
          { status: 201 },
        );
      }
      return new Response("{}");
    },
  );
  return bodies;
}

test("creates a shelf on the spot and adds with it", async () => {
  const bodies = stubApi();
  const user = renderForm();

  await user.click(
    await screen.findByRole("button", { name: "Add to a shelf" }),
  );
  await user.type(
    await screen.findByRole("combobox", { name: "Find or create a shelf" }),
    "Ensayo",
  );
  await user.click(
    await screen.findByRole("option", { name: /Create .Ensayo./ }),
  );
  await user.click(screen.getByRole("button", { name: /Add to library/ }));

  await waitFor(() => expect(bodies).toHaveLength(1));
  expect(JSON.parse(bodies[0]).shelf_ids).toEqual([5]);
});

test("sets notes, format and the domain's own date fields while adding", async () => {
  const bodies = stubApi();
  const user = renderForm();

  await user.type(screen.getByRole("textbox", { name: "Notes" }), "Finally.");
  await user.click(screen.getByRole("combobox", { name: "Format" }));
  await user.click(await screen.findByRole("option", { name: "Physical" }));
  await user.keyboard("{Escape}");
  await user.type(screen.getByLabelText("Finished"), "2026-02-03");
  await user.click(screen.getByRole("button", { name: /Add to library/ }));

  await waitFor(() => expect(bodies).toHaveLength(1));
  const body: Record<string, unknown> = JSON.parse(bodies[0]);
  expect(body.notes).toBe("Finally.");
  expect(body.formats).toEqual(["physical"]);
  expect(body.date_finished).toBe("2026-02-03");
});

test("offers a record none of the fields it has no meaning for", async () => {
  stubApi();
  renderForm({ itemType: "album" });

  // A relisten counter makes no sense, and the dates go with it (DEC-057). The
  // form asks the domain rather than branching on the type.
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Format" })).toBeVisible(),
  );
  expect(screen.queryByLabelText("Reread count")).toBeNull();
  expect(screen.queryByLabelText("Started")).toBeNull();
  expect(screen.queryByLabelText("Finished")).toBeNull();
});

test("the domain's own default status is what it opens on", async () => {
  const bodies = stubApi();
  const user = renderForm({ itemType: "album" });

  await user.click(screen.getByRole("button", { name: /Add to library/ }));
  await waitFor(() => expect(bodies).toHaveLength(1));
  // Not a literal `read`: the API refuses the other domain's default outright.
  expect(JSON.parse(bodies[0]).status).toBe("owned");
});

test("the add screen names the passage fields as the domain does", async () => {
  // Sprint 038's deliverable 5 claimed the entry panel's last hardcoded book word and
  // fixed the detail page and the opinion dialog only. This screen is the third render
  // site and kept saying "Reread count" to every domain.
  const anime = {
    ...book,
    id: "anime",
    label: "Anime",
    entry_field_labels: { reread_count: "Rewatches" },
  } as unknown as ItemType;
  renderForm({ itemType: "anime", itemTypes: [anime] });

  expect(await screen.findByLabelText("Rewatches")).toBeInTheDocument();
  expect(screen.queryByLabelText("Reread count")).toBeNull();
  // The neutral two are right for a series and are left alone.
  expect(screen.getByLabelText("Started")).toBeInTheDocument();
});
