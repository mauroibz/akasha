// Sprint 085 walkthrough: the owner's four asks, live, on a fresh data dir.
// 1. Typed entries import with no file (three album rows, by hand).
// 2. A dropped file fills the editor (the check-what-I-uploaded path).
// 3. The creators checkbox sends no_creators and the reader maps titles only.
// 4. The strip: custom list first, badges naming each connector's libraries.
//
// Requires: backend on 127.0.0.1:8002 (fresh AKASHA_DATA_DIR), vite on :5175
// with AKASHA_E2E_BACKEND=http://127.0.0.1:8002.

import { chromium } from "@playwright/test";

const BASE = "http://127.0.0.1:5175";
const API = "http://127.0.0.1:8002";

const problems = [];
const browser = await chromium.launch();
const page = await browser.newPage();
page.on("pageerror", (error) => problems.push(String(error)));
page.on("console", (message) => {
  if (message.type() === "error") {
    const url = message.location().url;
    const designed =
      url.includes("/api/auth/me") ||
      url.includes("/cover") ||
      /metahub\.space/.test(url) ||
      /coverartarchive/.test(url);
    if (!designed) problems.push(message.text());
  }
});

const api = (path, init) =>
  fetch(`${API}${path}`, init).then((response) => response.json());

// 4. The strip: order and badges.
await page.goto(`${BASE}/import`);
const strip = page.getByRole("tablist", { name: "Import source" });
const tabs = strip.getByRole("tab");
const first = await tabs.first().textContent();
if (!/custom list/i.test(first ?? "")) problems.push(`first tab is ${first}`);
if (!/any library/i.test(first ?? ""))
  problems.push("list tab lacks Any library badge");
const goodreads = await page
  .getByRole("tab", { name: /goodreads/i })
  .textContent();
if (!/book/i.test(goodreads ?? ""))
  problems.push("goodreads lacks Books badge");

// 1. Typed entries, no file: three film rows by hand.
await page.getByRole("tab", { name: /custom list/i }).click();
await page
  .getByRole("combobox", { name: /which library is this list for\?/i })
  .selectOption("movie");
await page
  .getByRole("textbox", { name: /or type your list here/i })
  .fill("Película\r\nBlade Runner\r\nSuspiria\r\nLa Ciénaga");
await page.getByRole("button", { name: /preview/i }).click();
await page
  .getByRole("button", { name: /import \d+ ready rows?/i })
  .waitFor({ timeout: 300_000 });
console.log("typed 3 film rows: search drained, commit gate open");
await page.getByRole("button", { name: /import \d+ ready rows?/i }).click();
await page
  .getByText(/import complete:/i)
  .first()
  .waitFor({ timeout: 60_000 });
const films = await api("/api/entries?status=unsorted&limit=200&type=movie");
console.log(`typed film rows committed: ${films.total}`);
if (films.total !== 3)
  problems.push(`expected 3 typed films, saw ${films.total}`);

// 3. The checkbox: another batch, book domain, two-column list, no_creators.
await page.goto(`${BASE}/import`);
// A fresh visit opens on the list (it leads the strip), so no tab click.
await page
  .getByRole("combobox", { name: /which library is this list for\?/i })
  .selectOption("book");
await page
  .getByRole("textbox", { name: /or type your list here/i })
  .fill("Título,Autor\r\nRayuela,Julio Cortázar");
await page.getByRole("checkbox", { name: /no creators column/i }).check();
await page.getByRole("button", { name: /preview/i }).click();
await page
  .getByRole("button", { name: /import \d+ ready rows?/i })
  .waitFor({ timeout: 300_000 });
console.log("checkbox batch: drained, committing");
await page.getByRole("button", { name: /import \d+ ready rows?/i }).click();
await page
  .getByText(/import complete:/i)
  .first()
  .waitFor({ timeout: 60_000 });
// The committed row must carry NO creators — the reader mapped titles only.
const books = await api("/api/entries?status=unsorted&limit=200&type=book");
const rayuela = books.items.find((entry) => entry.item.title === "Rayuela");
if (!rayuela) problems.push("Rayuela did not land from the checkbox batch");
else {
  const detail = await api(`/api/entries/${rayuela.id}`);
  const creators = detail.item.metadata?.creators ?? [];
  console.log(`Rayuela creators: ${JSON.stringify(creators)}`);
  if (creators.length)
    problems.push("no_creators batch still carried creators");
}

// 2. The file-fills-editor path (fixture file through the real input).
await page.goto(`${BASE}/import`);
await page
  .getByRole("combobox", { name: /which library is this list for\?/i })
  .selectOption("album");
const editor = page.getByRole("textbox", { name: /or type your list here/i });
const chooser = page.getByRole("button", {
  name: /your list \(csv or text\)/i,
});
await chooser.setInputFiles({
  name: "list_albums_es.csv",
  mimeType: "text/csv",
  buffer: Buffer.from(
    "Álbum,Artista\r\nKind of Blue,Miles Davis\r\nDiscovery,Daft Punk",
  ),
});
await page
  .getByRole("textbox", { name: /or type your list here/i })
  .waitFor({ timeout: 10_000 });
const editorValue = await editor.inputValue();
let filled = editorValue;
for (let i = 0; i < 20 && !filled.includes("Kind of Blue"); i++) {
  await page.waitForTimeout(250);
  filled = await editor.inputValue();
}
console.log(`editor after drop: ${JSON.stringify(filled.slice(0, 40))}`);
if (!filled.includes("Kind of Blue"))
  problems.push("a dropped file did not fill the editor");
// Correct one row inline and preview: the edited text is the source.
await editor.fill("Álbum,Artista\r\nKind of Blue,Miles Davis Quartet");
await page.getByRole("button", { name: /preview/i }).click();
await page
  .getByRole("button", { name: /import \d+ ready rows?/i })
  .waitFor({ timeout: 300_000 });
console.log("editor-correction batch: drained");

console.log(
  problems.length ? `PROBLEMS:\n${problems.join("\n")}` : "WALKTHROUGH CLEAN",
);
await browser.close();
process.exit(problems.length ? 1 : 0);
