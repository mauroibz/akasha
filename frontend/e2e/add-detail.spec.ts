import { type Page } from "@playwright/test";
import { expect, test } from "./console";

import { sampleAnimations } from "./motion";
import { albumItemType, stubItemTypes } from "./seed";

const candidate = (id: string, year: number) => ({
  source: "openlibrary",
  source_id: id,
  source_refs: [{ source: "openlibrary", source_id: id }],
  title: "Rayuela",
  subtitle: null,
  creators: ["Julio Cortázar"],
  year,
  cover_url: null,
  identifiers: {},
  language: "es",
  metadata: {},
});
const entry = {
  id: 7,
  item_id: 3,
  status: "reading",
  score: 8,
  notes: "Cached while providers are down",
  date_added: "2026-07-22",
  date_started: null,
  date_finished: null,
  reread_count: 0,
  score_provisional: false,
  suggested_status: null,
  item: {
    id: 3,
    type: "book",
    title: "Rayuela",
    subtitle: null,
    year: 1963,
    creator: "Julio Cortázar",
    cover_path: null,
    metadata: { creators: ["Julio Cortázar"], publisher: "Sudamericana" },
    identifiers: {},
    sources: [{ source: "openlibrary", source_id: "OL1M", is_primary: true }],
  },
  shelves: [],
  formats: [],
};

async function common(page: Page) {
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await stubItemTypes(page);
  // Keep this suite isolated from a developer's real library on the proxy target.
  // The selected-provider flow below needs an empty local result set; leaving this
  // request unstubbed made the answer depend on whatever happened to be on :8000.
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: [],
        next_cursor: null,
        total: 0,
        facets: {
          status_counts: {},
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
  await page.route("**/api/entries/7", (route) =>
    route.fulfill({ json: entry }),
  );
}

test("manual add is keyboard-complete and cached detail edits persist", async ({
  page,
}) => {
  await common(page);
  let posted = 0;
  await page.route("**/api/entries", async (route) => {
    posted += 1;
    await route.fulfill({
      status: 201,
      json: { entry, already_exists: false, near_matches: [] },
    });
  });
  await page.route("**/api/items/3", (route) =>
    route.fulfill({ json: { ...entry.item, title: "Rayuela corregida" } }),
  );
  // /add opens straight on the manual form, with the cursor already in it.
  await page.goto("/add");
  await expect(page.getByLabel(/^title$/i)).toBeFocused();
  await page.getByLabel(/^title$/i).fill("Rayuela");
  await page.getByRole("button", { name: /add to library/i }).press("Enter");
  // New entries return to the library with a success toast
  await expect(page).toHaveURL(/\/(\?type=[a-z]+)?$/);
  expect(posted).toBe(1);
  // Navigate to detail to verify the entry was created
  await page.goto("/books/7");
  await expect(page.getByText("Cached while providers are down")).toBeVisible();
  await page.getByRole("button", { name: /edit metadata/i }).click();
  await page.getByLabel(/^title$/i).fill("Rayuela corregida");
  await page.getByRole("button", { name: /save metadata/i }).click();
});

test("work resolution exposes edition choice and exact duplicate navigates", async ({
  page,
}) => {
  await common(page);
  await page.route("**/api/search/resolve?**", (route) =>
    route.fulfill({ json: [candidate("OL1M", 1963), candidate("OL2M", 1999)] }),
  );
  await page.route("**/api/entries", (route) =>
    route.fulfill({
      status: 200,
      json: { entry, already_exists: true, near_matches: [] },
    }),
  );
  // Resolving a pasted URL is one of the eleven behaviours that had to survive
  // the move onto `/` (Sprint 029, inventory row 2).
  await page.goto("/");
  await page.getByRole("searchbox").fill("https://openlibrary.org/works/OL1W");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /Rayuela.*1963/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Rayuela.*1999/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Rayuela.*1999/i }).click();
  await page.getByRole("button", { name: /add to library/i }).click();
  await expect(page).toHaveURL(/\/books\/7/);
  // The confirmation is a visible toast on the destination route. It used to be
  // an sr-only paragraph, which is why this assertion could not tell the
  // difference (DEC-024); e2e/feedback.spec.ts now checks the geometry too.
  await expect(
    page
      .locator("[data-sonner-toast]")
      .filter({ hasText: "Already in your library" }),
  ).toBeVisible();
});

test("mobile detail confirms refresh and reports cover failure without motion", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await common(page);
  await page.route("**/api/items/3/refresh", (route) =>
    route.fulfill({
      status: 502,
      json: { error: { code: "provider_failure" } },
    }),
  );
  await page.route("**/api/items/3/cover", (route) =>
    route.fulfill({ status: 422, json: { error: { code: "invalid_cover" } } }),
  );
  await page.goto("/books/7");
  await page.getByRole("button", { name: /refresh from provider/i }).click();
  await expect(
    page.getByRole("alertdialog", { name: /overwrite cached metadata/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /confirm refresh/i }).click();
  await expect(page.getByRole("alert")).toContainText("not changed");
  await page.getByLabel(/replace cover/i).setInputFiles({
    name: "bad.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("bad"),
  });
  await expect(page.getByRole("alert")).toContainText(
    "previous cover is unchanged",
  );
  await expect(page.locator("main")).toBeVisible();
});

test("choosing a cover from another edition installs it and closes the chooser", async ({
  page,
}) => {
  await common(page);
  let chosen: string | null = null;
  await page.route("**/api/items/3/cover-candidates", (route) =>
    route.fulfill({
      json: {
        candidates: [
          {
            cover_url: "https://covers.openlibrary.org/b/id/15104001-L.jpg",
            source_id: "OL59588323M",
            title: "Il gioco del mondo",
            year: 1969,
          },
          {
            cover_url: "https://covers.openlibrary.org/b/id/15103989-L.jpg",
            source_id: "OL59587941M",
            title: "Marelle",
            year: 1966,
          },
        ],
        reason: null,
      },
    }),
  );
  await page.route("**/api/items/3/cover", async (route) => {
    chosen = JSON.parse(route.request().postData() ?? "{}").cover_url;
    await route.fulfill({
      json: { ...entry.item, cover_url: "/api/items/3/cover" },
    });
  });

  await page.goto("/books/7");
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  await page.getByRole("button", { name: /choose a cover/i }).click();

  const chooser = page.getByRole("dialog");
  await expect(chooser).toBeVisible();
  await chooser.getByRole("button", { name: /1966 edition/i }).click();

  await expect(page.getByRole("dialog")).toBeHidden();
  expect(chosen).toBe("https://covers.openlibrary.org/b/id/15103989-L.jpg");
});

test("fetches a missing cover for a domain with no chooser, and reports why one fails", async ({
  page,
}) => {
  // A domain with no editions to choose from (`chooses_covers: false`, unlike
  // the book fixture above) offers "Fetch cover" instead, where there is no
  // cover installed and the item has something to fetch one from.
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [{ ...albumItemType, chooses_covers: false }] }),
  );
  const album = {
    id: 7,
    item_id: 3,
    status: "owned",
    score: null,
    notes: null,
    date_added: "2026-07-22",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    score_provisional: false,
    suggested_status: null,
    item: {
      id: 3,
      type: "album",
      title: "Discovery",
      subtitle: null,
      year: 2001,
      creator: "Daft Punk",
      cover_path: null,
      metadata: {},
      identifiers: {},
      sources: [{ source: "musicbrainz", source_id: "mb-1", is_primary: true }],
    },
    shelves: [],
    formats: ["vinyl"],
  };
  let coverFetched = false;
  await page.route("**/api/entries/7", (route) =>
    route.fulfill({
      json: coverFetched
        ? { ...album, item: { ...album.item, cover_url: "/api/items/3/cover" } }
        : album,
    }),
  );
  await page.goto("/books/7");
  await expect(page.getByRole("heading", { name: "Discovery" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Choose a cover" }),
  ).toBeHidden();

  await page.route("**/api/items/3/cover/fetch", (route) =>
    route.fulfill({
      status: 422,
      json: {
        error: {
          code: "cover_unavailable",
          message: "The provider has no cover for this item",
        },
      },
    }),
  );
  await page.getByRole("button", { name: "Fetch cover" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "The provider has no cover for this item",
  );

  await page.route("**/api/items/3/cover/fetch", (route) => {
    coverFetched = true;
    return route.fulfill({
      json: { ...album.item, cover_url: "/api/items/3/cover" },
    });
  });
  await page.getByRole("button", { name: "Fetch cover" }).click();
  await expect(
    page.locator("aside img[alt='Cover of Discovery']"),
  ).toHaveAttribute("src", "/api/items/3/cover");
});

test("search results stagger in and selecting one keeps the keyboard flow", async ({
  page,
}) => {
  await common(page);
  await page.route("**/api/search**", (route) =>
    route.fulfill({
      json: Array.from({ length: 6 }, (_, index) =>
        candidate(`OL${index + 1}M`, 1963 + index),
      ),
    }),
  );
  await page.goto("/");

  const samples = await sampleAnimations(page, async () => {
    await page.getByRole("searchbox").fill("Rayuela");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(
      page.getByRole("button", { name: /None of these/ }),
    ).toBeVisible();
    await expect(page.locator("[data-results-grid] button")).toHaveCount(7);
  });
  // Six results plus the manual fallback, each entering in its own right. The
  // fallback is part of the list, so it arrives last rather than ahead of the
  // results it follows.
  expect(samples.length).toBeGreaterThan(0);

  await page
    .getByRole("button", { name: /Rayuela/ })
    .first()
    .click();
  // The form animates in, but nothing waits for it: focus is where a keyboard
  // reader needs it on the frame the form mounts.
  await expect(page.getByRole("combobox", { name: /status/i })).toBeFocused();
});

test("a file can be attached, downloaded and removed from the detail page", async ({
  page,
}) => {
  await common(page);
  let attachments: Array<Record<string, unknown>> = [];
  await page.route("**/api/items/3/attachments", async (route) => {
    if (route.request().method() === "POST") {
      attachments = [
        {
          id: 1,
          filename: "Rayuela.epub",
          byte_size: 2621440,
          sha256: "a".repeat(64),
          created_at: "2026-08-14T00:00:00Z",
        },
      ];
      await route.fulfill({ status: 201, json: attachments[0] });
      return;
    }
    await route.fulfill({ json: { attachments } });
  });
  await page.route("**/api/items/3/attachments/1", async (route) => {
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON() as { filename: string };
      attachments = [{ ...attachments[0], filename: body.filename }];
      await route.fulfill({ json: attachments[0] });
      return;
    }
    attachments = [];
    await route.fulfill({ status: 204, body: "" });
  });

  await page.goto("/books/7");
  await expect(page.getByRole("heading", { name: "Rayuela" })).toBeVisible();
  await expect(page.getByText("No files attached yet.")).toBeVisible();

  await page.getByTestId("attachment-picker").setInputFiles({
    name: "Rayuela.epub",
    mimeType: "application/epub+zip",
    buffer: Buffer.from("epub bytes"),
  });

  const link = page.getByRole("link", { name: "Rayuela.epub" });
  await expect(link).toBeVisible();
  await expect(page.getByText("2.5 MB")).toBeVisible();

  // The link points at the item-scoped download and carries `download`, which is
  // all the client is responsible for. That the response forces a save rather
  // than rendering is the server's contract and is asserted against the real
  // headers in `backend/tests/test_attachments_api.py`, where it can be checked
  // properly instead of inferred from browser behaviour.
  await expect(link).toHaveAttribute("href", "/api/items/3/attachments/1");
  await expect(link).toHaveAttribute("download", "");

  // Renaming is inline and the download URL does not move: the name is metadata,
  // so the row keeps its identity and only what it is called changes.
  await page.getByRole("button", { name: "Rename Rayuela.epub" }).click();
  const field = page.getByLabel("New name for Rayuela.epub");
  await field.fill("Rayuela — Julio Cortázar.epub");
  await page.getByRole("button", { name: "Save" }).click();

  const renamed = page.getByRole("link", {
    name: "Rayuela — Julio Cortázar.epub",
  });
  await expect(renamed).toBeVisible();
  await expect(renamed).toHaveAttribute("href", "/api/items/3/attachments/1");

  // Removing asks first, the way *Delete entry* on this page already does:
  // once it is the last reference the bytes are gone, and the product spec
  // reserves confirmation for exactly that (§7 interaction notes).
  await page
    .getByRole("button", { name: "Remove Rayuela — Julio Cortázar.epub" })
    .click();
  await expect(
    page.getByRole("alertdialog", { name: /Remove this file/ }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(renamed).toBeVisible();

  await page
    .getByRole("button", { name: "Remove Rayuela — Julio Cortázar.epub" })
    .click();
  await page.getByRole("button", { name: "Remove file" }).click();
  await expect(page.getByText("No files attached yet.")).toBeVisible();
});
