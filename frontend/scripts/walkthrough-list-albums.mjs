// Sprint 084 AC9 walkthrough: a hand-written ALBUM list, end to end, against
// a live backend on a fresh data dir — the whole search-then-confirm flow on
// a non-book domain, proving the pipeline is domain-blind with live provider
// boundaries (MusicBrainz for the search; covers arrive via enrichment).
//
// Requires: backend on 127.0.0.1:8002 (fresh AKASHA_DATA_DIR=/tmp/akasha-s084),
// frontend dev server on 127.0.0.1:5175 with AKASHA_E2E_BACKEND=http://127.0.0.1:8002.

import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";

const BASE = "http://127.0.0.1:5175";
const API = "http://127.0.0.1:8002";
const CSV = readFileSync(
  new URL(
    "../../backend/tests/fixtures/imports/list_albums_es.csv",
    import.meta.url,
  ),
);

const problems = [];
const browser = await chromium.launch();
const page = await browser.newPage();
page.on("console", (message) => {
  if (message.type() === "error") {
    const url = message.location().url;
    const designed =
      url.includes("/api/auth/me") ||
      url.includes("/cover") ||
      /metahub\.space\/poster/.test(url) ||
      /coverartarchive/.test(url);
    if (!designed) problems.push(message.text());
  }
});
page.on("pageerror", (error) => problems.push(String(error)));

const api = (path, init) =>
  fetch(`${API}${path}`, init).then((response) => response.json());

// 1. Pick the album library, then upload through the real UI.
await page.goto(`${BASE}/import`);
await page.getByRole("tab", { name: /custom list/i }).click();
await page
  .getByRole("combobox", { name: /which library is this list for\?/i })
  .selectOption("album");
// The mapping labels speak the album domain's own words.
await page.getByText(/artists is column/i).waitFor({ timeout: 10000 });

const chooser = page.getByRole("button", {
  name: /your list \(csv or text\)/i,
});
await chooser.setInputFiles({
  name: "list_albums_es.csv",
  mimeType: "text/csv",
  buffer: CSV,
});
await page.getByRole("button", { name: /preview/i }).click();

// 2. The batch previews in `matching`; a 4-row job drains fast, so the banner
// may already have flipped.
await page
  .getByText(/searching for matches/i)
  .waitFor({ timeout: 10000 })
  .then(() => console.log("preview: matching banner visible"))
  .catch(() => console.log("preview: already drained (4 rows search fast)"));

// 3. The real job runner searches MusicBrainz; the poll drains to previewed.
await page
  .getByRole("button", { name: /import \d+ ready rows?/i })
  .waitFor({ timeout: 300000 });
console.log("search drained; commit gate open");

// 4. Confirm one row through the real cards (Kind of Blue), leave the rest.
const cards = page.getByRole("article");
console.log(`rows rendered: ${await cards.count()}`);
const kindCard = cards.filter({ hasText: "Kind of Blue" });
const confirmCount = await kindCard
  .getByRole("button", { name: /^confirm$/i })
  .count();
if (confirmCount === 0) {
  problems.push("Kind of Blue has no Confirm control — no proposals?");
} else {
  await kindCard
    .getByRole("button", { name: /^confirm$/i })
    .first()
    .click();
  await page.getByText("Confirmed").first().waitFor({ timeout: 15000 });
  console.log("confirmed: Kind of Blue (MusicBrainz payload)");
}

// 5. Commit.
await page.getByRole("button", { name: /import \d+ ready rows?/i }).click();
await page
  .getByText("Import complete:", { exact: false })
  .first()
  .waitFor({ timeout: 60000 });
const committed = await api(
  "/api/entries?status=unsorted&limit=200&type=album",
);
console.log(`album unsorted after commit: ${committed.total}`);
if (committed.total !== 4)
  problems.push(`expected 4 album entries, saw ${committed.total}`);
for (const entry of committed.items) {
  if (entry.item.type !== "album")
    problems.push(
      `${entry.item.title} landed as ${entry.item.type}, not album`,
    );
}
const kind = committed.items.find(
  (entry) => entry.item.title === "Kind of Blue",
);
if (kind) {
  const detail = await api(`/api/entries/${kind.id}`);
  console.log(
    `Kind of Blue: identifiers=${JSON.stringify(detail.item.identifiers)} cover=${detail.item.cover_url ? "yes" : "no"}`,
  );
  // MusicBrainz release-groups carry no global identifier (obs. 3), so the
  // designed outcome for a confirmed album row is: creators from the
  // proposal, no identifier (the domain's own enrichment is Spotify-keyed
  // and never fires for a search-confirmed album — DEC-052), and a cover
  // installed from the confirmed card's own cover_url (Sprint 084's
  // confirm-stages-cover channel).
  if (!detail.item.cover_url) problems.push("the confirmed album has no cover");
  const creators = detail.item.metadata?.creators ?? [];
  if (!creators.includes("Miles Davis"))
    problems.push(`Kind of Blue carries creators ${JSON.stringify(creators)}`);
} else {
  problems.push("Kind of Blue did not land");
}

// 6. Undo restores the pre-import state.
const undo = await page
  .getByRole("button", { name: /undo this import/i })
  .click()
  .then(() => page.getByRole("button", { name: /confirm undo/i }).click())
  .then(() =>
    page
      .getByRole("heading", { name: /import undone/i })
      .waitFor({ timeout: 60000 }),
  )
  .then(() => true)
  .catch(() => false);
if (!undo) problems.push("the undo control did not complete");
const after = await api("/api/entries?status=unsorted&limit=200&type=album");
console.log(`album unsorted after undo: ${after.total}`);
if (after.total !== 0) problems.push(`undo left ${after.total} rows behind`);

console.log(
  problems.length ? `PROBLEMS:\n${problems.join("\n")}` : "WALKTHROUGH CLEAN",
);
await browser.close();
process.exit(problems.length ? 1 : 0);
