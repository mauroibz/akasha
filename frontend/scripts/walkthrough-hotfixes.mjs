// Walkthrough for the two hotfixes, against the live backend on :8001 and the
// dev frontend on :5174 — real data, real API, no stubs (DEC-025). Seeded rows
// carry a run-unique prefix so the script is re-runnable against a data dir a
// previous run already touched.
import { chromium } from "@playwright/test";

const BASE = "http://127.0.0.1:5174";
const API = "http://127.0.0.1:8001";
const RUN = `WT${Date.now().toString(36)}`;

function api(path) {
  return `${API}${path}`;
}

async function unsortedTotal() {
  const response = await fetch(api("/api/entries?status=unsorted&limit=200"));
  const data = await response.json();
  return data;
}

const browser = await chromium.launch();
const page = await browser.newPage();
const problems = [];
page.on("console", (message) => {
  if (message.type() === "error") {
    // Two designed 404s reach the console as bare resource-load errors (the
    // text carries no URL; it lives on the message's location): auth is off
    // (`/api/auth/me` answers 404 by contract, technical spec 7.1) and a manual
    // add has no cover (the 404 *is* "no cover"). Anything else is a finding.
    const url = message.location().url;
    const designed = url.includes("/api/auth/me") || url.includes("/cover");
    if (!designed) problems.push(message.text());
  }
});
page.on("pageerror", (error) => problems.push(String(error)));

// Seed five rows through the real API, exactly the way an import leaves them.
for (let index = 1; index <= 5; index += 1) {
  const response = await fetch(api("/api/entries"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      manual: {
        item_type: "book",
        title: `${RUN} Book ${index}`,
        metadata: { creators: [`Author ${index}`] },
      },
      status: "unsorted",
      idempotency_key: `${RUN}-${index}`,
    }),
  });
  if (response.status !== 201)
    problems.push(`seed ${index} answered ${response.status}`);
}

// --- Hotfix 2 first half: triage row -> detail -> back returns to triage ---
await page.goto(`${BASE}/import?tab=triage`);
await page.getByRole("heading", { name: /inbox/i }).waitFor({ timeout: 15000 });
const rendered = await page.locator("[data-entry-id]").count();
console.log(`triage rows rendered: ${rendered}`);
if (rendered < 5) problems.push(`expected at least 5 rows, saw ${rendered}`);

await page.getByText(`${RUN} Book 1`, { exact: true }).click();
await page.waitForURL(/\/books\/\d+$/, { timeout: 15000 });
const entryUrl = page.url();
console.log("opened detail:", entryUrl);
const backLink = page.getByRole("link", { name: /← triage/i });
await backLink.waitFor({ timeout: 5000 });
console.log("detail back link text:", await backLink.textContent());
await backLink.click();
await page.waitForURL(/\/import\?tab=triage$/, { timeout: 5000 });
console.log("back landed on:", page.url());

// --- Hotfix 1: selection -> red Discard -> confirm -> rows really gone ---
const before = await unsortedTotal();
await page
  .locator(`[data-entry-id]`)
  .filter({ hasText: `${RUN} Book 2` })
  .locator('[role="checkbox"]')
  .click();
await page
  .locator(`[data-entry-id]`)
  .filter({ hasText: `${RUN} Book 3` })
  .locator('[role="checkbox"]')
  .click();
await page.getByText("2 selected").waitFor({ timeout: 5000 });
const discard = page.getByRole("button", { name: /^Discard$/ });
await discard.waitFor({ timeout: 5000 });
// The e2e spec already pins the painted colour; here it is only logged for the
// walkthrough record, read through the one browser API the callback scope has.
const styles = await discard.evaluate((el) => {
  const computed = el.ownerDocument.defaultView.getComputedStyle(el);
  return { bg: computed.backgroundColor, ink: computed.color };
});
console.log(`discard button bg=${styles.bg} ink=${styles.ink}`);
if (styles.bg !== "rgb(239, 68, 68)")
  problems.push(`discard bg was ${styles.bg}`);

// The dialog is the guard: Cancel must leave everything in place.
await discard.click();
const dialog = page.getByRole("alertdialog");
await dialog.waitFor({ timeout: 5000 });
console.log("dialog title:", await dialog.getByRole("heading").textContent());
await dialog.getByRole("button", { name: /cancel/i }).click();
await page
  .getByRole("alertdialog")
  .waitFor({ state: "detached", timeout: 5000 });
const afterCancel = await unsortedTotal();
console.log(`after cancel, unsorted total: ${afterCancel.total}`);
if (afterCancel.total !== before.total)
  problems.push(
    `cancel leaked a delete: ${before.total} -> ${afterCancel.total}`,
  );

// Now confirm for real.
await discard.click();
await page
  .getByRole("alertdialog")
  .getByRole("button", { name: /discard/i })
  .click();
await page.getByText("2 entries discarded").waitFor({ timeout: 5000 });
await page.waitForTimeout(600);
const afterDiscard = await unsortedTotal();
console.log(`after confirm, unsorted total: ${afterDiscard.total}`);
if (afterDiscard.total !== before.total - 2)
  problems.push(`expected ${before.total - 2} left, saw ${afterDiscard.total}`);
const discardedGone =
  afterDiscard.items.filter((entry) =>
    [`${RUN} Book 2`, `${RUN} Book 3`].includes(entry.item.title),
  ).length === 0;
if (!discardedGone) problems.push("a discarded row is still in the inbox");

// The remaining rows still work: one row's detail still returns to triage.
await page.getByText(`${RUN} Book 4`, { exact: true }).click();
await page.waitForURL(/\/books\/\d+$/, { timeout: 5000 });
await page.getByRole("link", { name: /← triage/i }).click();
await page.waitForURL(/\/import\?tab=triage$/, { timeout: 5000 });

// Hotfix 2 second half: a deep link (no state) still offers ← Library.
const keptEntry = afterDiscard.items.find((entry) =>
  entry.item.title.startsWith(`${RUN} Book 1`),
);
await page.goto(`${BASE}/books/${keptEntry.id}`);
const libraryLink = page.getByRole("link", { name: /← library/i });
await libraryLink.waitFor({ timeout: 5000 });
console.log("deep link back text:", await libraryLink.textContent());

console.log(
  problems.length ? `PROBLEMS:\n${problems.join("\n")}` : "WALKTHROUGH CLEAN",
);
await browser.close();
process.exit(problems.length ? 1 : 0);
