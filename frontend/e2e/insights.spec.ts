import { expect, test } from "./console";
import {
  albumItemType,
  animeItemType,
  movieItemType,
  seriesItemType,
  stubItemTypes,
} from "./seed";

/**
 * The insights screen at the sizes and in the states a person actually uses it
 * (Sprint 066). The a11y half lives in `accessibility.spec.ts` beside every other
 * screen's; this file is layout and behaviour against a real browser.
 */

const bookType = {
  id: "book",
  label: "Book",
  fields: [
    {
      name: "creators",
      label: "Authors",
      type: "text",
      multiplicity: "many",
      groupable: true,
    },
    {
      name: "subjects",
      label: "Subjects",
      type: "text",
      multiplicity: "many",
      groupable: true,
    },
    {
      name: "language",
      label: "Language",
      type: "text",
      multiplicity: "one",
      groupable: true,
    },
  ],
  statuses: [{ value: "read", label: "Read", choosable: true, hotkey: "r" }],
  default_status: "read",
  entry_fields: [],
  entry_field_labels: {},
  progress: null,
  formats: [],
  entry_panel_label: "Your reading data",
  chooses_covers: true,
};

const rankings: Record<
  string,
  Array<[string, number, number, number | null]>
> = {
  creators: [
    ["Julio Cortázar", 7, 6, 8.8],
    ["Ursula K. Le Guin", 5, 5, 9.2],
    ["China Miéville", 4, 2, 6.5],
    ["Italo Calvino", 3, 3, 7.7],
    ["Ted Chiang", 2, 2, 9.5],
    ["Gene Wolfe", 2, 1, 5],
    ["Samanta Schweblin", 2, 0, null],
  ],
  subjects: [
    ["Fiction", 21, 16, 8.4],
    ["Science fiction", 14, 11, 8.9],
    ["Argentina", 9, 8, 8.6],
    ["Short stories", 8, 7, 9],
  ],
  // Two values: a fact, not a ranking. Belongs in the quiet line.
  language: [
    ["Spanish", 31, 20, 8.6],
    ["English", 16, 9, 8.1],
  ],
  year: [["1963", 2, 2, 9.5]],
  decade: [
    ["1960s", 11, 9, 9.1],
    ["1970s", 9, 8, 8.8],
    ["2000s", 8, 6, 7.5],
  ],
};

async function stubInsights(
  page: import("@playwright/test").Page,
  types: unknown[] = [bookType],
) {
  await stubItemTypes(page, types as Parameters<typeof stubItemTypes>[1]);
  await page.route("**/api/insights**", (route) => {
    const key = new URL(route.request().url()).searchParams.get("key") ?? "";
    route.fulfill({
      json: {
        type: "book",
        key,
        metric: "count",
        min_rated: 2,
        rows: (rankings[key] ?? []).map(([label, count, rated, mean]) => ({
          // A decade's real key is its plain start year ("1960"), not its
          // label ("1960s") -- `chronologyBuckets` reads it as a number.
          key: key === "decade" ? label.replace(/s$/, "") : label.toLowerCase(),
          label,
          count,
          rated_count: rated,
          mean_score: mean,
          score_spread: mean === null ? null : 1,
          covers: [],
        })),
        next_cursor: null,
        suppressed: [],
        no_rated_groups: false,
        null_count: key === "year" || key === "decade" ? 4 : 0,
        total_entries: 60,
        rated_entries: 47,
      },
    });
  });
  // Registered after the broader route above, so Playwright's
  // most-recently-registered-wins rule gives this the more specific match.
  await page.route("**/api/insights/scores**", (route) =>
    route.fulfill({
      json: {
        type: "book",
        counts: [0, 0, 2, 1, 3, 5, 8, 12, 9, 6],
        rated_count: 46,
        unrated_count: 14,
      },
    }),
  );
  await page.route("**/api/entries?**", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: 1,
            item_id: 1,
            status: "read",
            score: 10,
            notes: null,
            date_added: "2026-01-01",
            date_started: null,
            date_finished: null,
            reread_count: 0,
            progress: null,
            score_provisional: false,
            suggested_status: null,
            shelves: [],
            formats: [],
            item: {
              id: 1,
              type: "book",
              title: "Rayuela",
              subtitle: null,
              year: 1963,
              creator: "Julio Cortázar",
              cover_url: null,
              metadata: {},
              identifiers: {},
              sources: [],
            },
          },
        ],
        next_cursor: null,
        total: 7,
        facets: {
          status_counts: {},
          status_counts_by_type: {},
          format_counts: {},
        },
      },
    }),
  );
}

test("the page fits a phone, and nothing makes the body scroll sideways — five domains, DEC-134", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  // DEC-134 measured the overflow with five real domains; the checked-in
  // suite ran this page with one and stayed green through both redesign
  // sprints without ever exercising the defect. Five is what actually
  // reproduces it (Sprint 070, finding 9).
  await stubInsights(page, [
    bookType,
    albumItemType,
    animeItemType,
    movieItemType,
    seriesItemType,
  ]);
  await page.goto("/insights");
  await page.getByRole("heading", { name: "Authors" }).waitFor();

  const strip = page.getByRole("radiogroup", { name: "Choose a domain" });
  await expect(strip.getByRole("radio")).toHaveCount(5);

  // The row labels are the widest thing on the page and they truncate rather
  // than push the layout out.
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

  // The strip itself scrolls within its own box instead of overflowing it
  // (DEC-134's fix): its scrollable content is wider than the box, and the
  // box itself never grows past the viewport.
  const stripBox = await strip.evaluate((node) => ({
    scrollWidth: node.scrollWidth,
    clientWidth: node.clientWidth,
    boundingWidth: node.getBoundingClientRect().width,
  }));
  expect(stripBox.scrollWidth).toBeGreaterThan(stripBox.clientWidth);
  expect(stripBox.boundingWidth).toBeLessThanOrEqual(390);

  // Cards stack rather than sit two abreast at this width.
  const boxes = await page
    .locator("[data-insight-card]")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().x),
    );
  expect(boxes.length).toBeGreaterThan(1);
  expect(new Set(boxes).size).toBe(1);

  // Every control a finger has to hit keeps its target. Scoped to the screen's
  // own controls: the shell's data-credit links are words inside a sentence, and
  // belong to the footer on every screen rather than to this one.
  const short = await page.evaluate(() =>
    [...document.querySelectorAll("main button, main a[href]")]
      .filter((node) => (node as HTMLElement).offsetParent !== null)
      .map((node) => ({
        text: (node.textContent ?? "").trim().slice(0, 30),
        height: node.getBoundingClientRect().height,
      }))
      .filter((row) => row.height > 0 && row.height < 44),
  );
  expect(short).toEqual([]);

  // The Decade/Year grain toggle (Sprint 073 deliverable 2) is one of the
  // controls just checked for a 44px target; exercising it here proves it
  // also holds the 390px body-overflow contract once its content swaps.
  const decadeCard = page
    .getByRole("heading", { name: "Decade" })
    .locator("xpath=ancestor::*[@data-chronology-card]");
  await decadeCard.getByRole("button", { name: "Year" }).click();
  await expect(decadeCard.getByText("1963")).toBeVisible();

  const overflowAfterToggle = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflowAfterToggle).toBeLessThanOrEqual(0);
});

test("a row opens in place, and the library says what it was opened into", async ({
  page,
}) => {
  await stubInsights(page);
  await page.goto("/insights");

  const row = page.getByRole("button", { name: /^Julio Cortázar: 7 entries/ });
  await row.click();
  await expect(page.getByText("Rayuela")).toBeVisible();
  await expect(page).toHaveURL(/\/insights$/);

  await page.getByRole("link", { name: /Open all 7 in the library/ }).click();
  await expect(
    page.getByRole("button", { name: /Insights · Authors · Julio Cortázar/ }),
  ).toBeVisible();
});
