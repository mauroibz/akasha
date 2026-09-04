import { expect, test } from "./console";
import { stubItemTypes } from "./seed";

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

async function stubInsights(page: import("@playwright/test").Page) {
  await stubItemTypes(page, [bookType]);
  await page.route("**/api/insights**", (route) => {
    const key = new URL(route.request().url()).searchParams.get("key") ?? "";
    route.fulfill({
      json: {
        type: "book",
        key,
        metric: "count",
        min_rated: 2,
        rows: (rankings[key] ?? []).map(([label, count, rated, mean]) => ({
          key: label.toLowerCase(),
          label,
          count,
          rated_count: rated,
          mean_score: mean,
          score_spread: mean === null ? null : 1,
        })),
        next_cursor: null,
        suppressed: [],
        no_rated_groups: false,
        null_count: key === "year" || key === "decade" ? 4 : 0,
      },
    });
  });
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

test("the page fits a phone, and nothing makes the body scroll sideways", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await stubInsights(page);
  await page.goto("/insights");
  await page.getByText("Julio Cortázar").waitFor();

  // The row labels are the widest thing on the page and they truncate rather
  // than push the layout out.
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

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
