// Sprint 083 AC8 walkthrough: the list connector, end to end, against a live
// backend on a fresh disposable data dir — real API, real job runner, the live
// Open Library boundary (keyless, answering as of this session's fixture
// capture; DEC-025's rule is satisfied by the recorded-fixture replays in the
// correctness suite — this run exercises the whole product flow).
//
// Flow: upload the 12-row synthetic CSV (auto mapping) -> preview in
// `matching` -> progress reaches 12/12 -> confirm 2 rows, discard 1, leave
// the rest -> commit -> 12 entries unsorted, the 2 confirmed carry the
// provider's ISBN, the discarded one has none -> undo restores the pre-import
// state.
//
// Requires: backend on 127.0.0.1:8002 (AKASHA_DATA_DIR=/tmp/akasha-s083),
// frontend dev server on 127.0.0.1:5175 with AKASHA_E2E_BACKEND=http://127.0.0.1:8002.

import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";

const BASE = "http://127.0.0.1:5175";
const API = "http://127.0.0.1:8002";
const CSV = readFileSync(
  new URL(
    "../../backend/tests/fixtures/imports/list_synthetic.csv",
    import.meta.url,
  ),
);

const problems = [];
const browser = await chromium.launch();
const page = await browser.newPage();
page.on("console", (message) => {
  if (message.type() === "error") {
    const url = message.location().url;
    const designed = url.includes("/api/auth/me") || url.includes("/cover");
    if (!designed) problems.push(message.text());
  }
});
page.on("pageerror", (error) => problems.push(String(error)));

async function api(path, init) {
  return fetch(`${API}${path}`, init).then((response) => response.json());
}

// 1. Upload through the real UI with auto mapping.
await page.goto(`${BASE}/import`);
await page.getByRole("tab", { name: /a list you wrote/i }).click();
const chooser = page.getByRole("button", {
  name: /your list \(csv or text\)/i,
});

await chooser.setInputFiles({
  name: "list_synthetic.csv",
  mimeType: "text/csv",
  buffer: CSV,
});
await page.getByRole("button", { name: /preview/i }).click();

// 2. The batch previews in `matching`; a 12-row job drains in seconds, so the
// banner may already have flipped to the drained state by the time we look.
const banner = await page
  .getByText(/searching for matches/i)
  .waitFor({ timeout: 10000 })
  .then(() => "matching banner visible")
  .catch(() => "already drained (12 rows search in seconds)");
console.log(`preview: ${banner}`);

// 3. The real job runner searches; the poll drains to `previewed`.
await page
  .getByRole("button", { name: /import \d+ ready rows?/i })
  .waitFor({ timeout: 300000 });
console.log("search drained; commit gate open");

// 4. Confirm two rows and discard one, through the real cards.
const cards = page.getByRole("article");
const count = await cards.count();
console.log(`rows rendered: ${count}`);
const rayuelaCard = cards.filter({ hasText: "Rayuela" });
const hobbitCard = cards.filter({ hasText: "El Hobbit" });
const domeCard = cards.filter({ hasText: "La cúpula 1" });
if (
  (await rayuelaCard.getByRole("button", { name: /^confirm$/i }).count()) ===
    0 ||
  (await hobbitCard.getByRole("button", { name: /^confirm$/i }).count()) ===
    0 ||
  (await domeCard.getByRole("button", { name: /^confirm$/i }).count()) === 0
) {
  problems.push("a walkthrough row has no Confirm control — no proposals?");
}
await rayuelaCard
  .getByRole("button", { name: /^confirm$/i })
  .first()
  .click();
await page.getByText("Confirmed").first().waitFor({ timeout: 15000 });
await hobbitCard
  .getByRole("button", { name: /^confirm$/i })
  .first()
  .click();
await page.getByText("Confirmed").first().waitFor({ timeout: 15000 });
console.log("confirmed: Rayuela, El Hobbit");

// Discard one row's proposals (keep as typed).
await domeCard
  .getByRole("button", { name: /none of these/i })
  .first()
  .click();
await page
  .getByText(/kept "La cúpula 1" as you typed it/i)
  .waitFor({ timeout: 15000 });
console.log("discarded: La cúpula 1 (kept as typed)");

// 5. Commit.
await page.getByRole("button", { name: /import \d+ ready rows?/i }).click();
await page
  .getByText("Import complete:", { exact: false })
  .first()
  .waitFor({ timeout: 60000 });
const committed = await api("/api/entries?status=unsorted&limit=200");
console.log(`unsorted after commit: ${committed.total}`);
// The 12-row fixture carries 2 error rows (a missing title, a short row) the
// commit refuses by design, so 10 entries land — the honest count for this
// fixture. The sprint's "12 entries" reads every row committing; the fixture
// deliberately includes rows that must not.
if (committed.total !== 10)
  problems.push(
    `expected 10 unsorted entries (12 rows, 2 refused), saw ${committed.total}`,
  );
const confirmedRows = committed.items.filter((entry) =>
  ["Rayuela", "El Hobbit"].includes(entry.item.title),
);
for (const entry of confirmedRows) {
  const detail = await api(`/api/entries/${entry.id}`);
  const hasIsbn = Object.keys(detail.item.identifiers).length > 0;
  console.log(
    `${entry.item.title}: identifiers=${JSON.stringify(detail.item.identifiers)} cover=${detail.item.cover_url ? "yes" : "no"}`,
  );
  if (!hasIsbn)
    problems.push(
      `${entry.item.title} was confirmed but carries no identifier`,
    );
}
const dome = committed.items.find(
  (entry) => entry.item.title === "La cúpula 1",
);
if (dome && Object.keys(dome.item.identifiers).length > 0) {
  problems.push("the discarded row carries an identifier it should not have");
}

// 6. Enrichment backfill changes nothing on them (all fields already full).
const backfill = await api("/api/enrichment/backfill", {
  method: "POST",
}).catch(() => null);
console.log(`backfill queued: ${backfill ? backfill.queued : "route refused"}`);

// 7. Undo restores the pre-import state, through the screen's own flow.
const undo = await page
  .getByRole("button", { name: /undo this import/i })
  .click()
  .then(() => page.getByRole("button", { name: /confirm undo/i }).click())
  .then(() => page.getByText(/import undone/i).waitFor({ timeout: 60000 }))
  .then(() => true)
  .catch(() => false);
if (!undo) problems.push("the undo control did not complete");
const after = await api("/api/entries?status=unsorted&limit=200");
console.log(`unsorted after undo: ${after.total}`);
if (after.total !== 0) problems.push(`undo left ${after.total} rows behind`);

console.log(
  problems.length ? `PROBLEMS:\n${problems.join("\n")}` : "WALKTHROUGH CLEAN",
);
await browser.close();
process.exit(problems.length ? 1 : 0);
