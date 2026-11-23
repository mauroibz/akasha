import AxeBuilder from "@axe-core/playwright";
import { type Page } from "@playwright/test";

import { expect, isHome, test } from "./console";
import { entry as seededEntry } from "./seed";

/**
 * Home (Sprints 130-131, DEC-183): the screen Akasha opens on. Renders from one
 * `GET /api/home`; *Start* and *Finished* change the entry; a library tile opens
 * the filtered library; *Personalize* reorders (keys and drag), resizes, removes and adds
 * modules, stored so a reload keeps them; no horizontal scroll and no serious axe
 * violations at 390px and 1440px in both themes, with and without the panel open.
 */

const status = (
  value: string,
  label: string,
  flags: Record<string, boolean> = {},
) => ({
  value,
  label,
  choosable: value !== "unsorted",
  hotkey: null,
  ...flags,
});

const types = [
  {
    id: "book",
    label: "Book",
    plural_label: "Books",
    fields: [],
    statuses: [
      status("unsorted", "Inbox"),
      status("read", "Read", { finished: true }),
      status("reading", "Reading", { in_progress: true }),
      status("to_read", "To read", { planned: true }),
    ],
    default_status: "to_read",
    entry_fields: ["date_started", "date_finished", "reread_count"],
    entry_field_labels: {},
    progress: { label: "Pages read", unit_label: "page", total_field: null },
    formats: [],
    entry_panel_label: "Your reading data",
    chooses_covers: false,
  },
  {
    id: "anime",
    label: "Anime",
    plural_label: "Anime",
    fields: [],
    statuses: [
      status("unsorted", "Inbox"),
      status("watching", "Watching", { in_progress: true }),
      status("completed", "Completed", { finished: true }),
      status("plan_to_watch", "Plan to watch", { planned: true }),
    ],
    default_status: "plan_to_watch",
    entry_fields: ["date_started", "date_finished"],
    entry_field_labels: {},
    progress: {
      label: "Episodes watched",
      unit_label: "episode",
      total_field: null,
    },
    formats: [],
    entry_panel_label: "Your watch data",
    chooses_covers: false,
  },
];

function entry(
  id: number,
  title: string,
  type: string,
  values: Record<string, unknown>,
) {
  const base = seededEntry(id);
  return {
    ...base,
    status: "reading",
    score: null,
    progress: null,
    unknown_fields: [],
    ...values,
    item: { ...base.item, type, title, creator: "Someone" },
  };
}

const reading = entry(1, "Designing Data-Intensive Applications", "book", {
  status: "reading",
  date_started: "2026-10-22",
  progress: 120,
});
const pile = entry(10, "Mistborn", "book", { status: "to_read" });
const months = Array.from({ length: 12 }, (_, index) => ({
  month: index + 1,
  count: 0,
  counts: {},
  covers: [] as unknown[],
}));
months[10] = {
  month: 11,
  count: 1,
  counts: { book: 1 },
  covers: [
    {
      entry_id: 21,
      item_id: 21,
      item_type: "book",
      title: "Pálido fuego",
      cover_url: null,
      score: 7,
    },
  ],
};

const home = {
  greeting: {
    today: "2026-11-22",
    active: { entry: reading, day: 32 },
    entries: 186,
    pile: 42,
    goals: [{ item_type: "book", target: 24, count: 1 }],
  },
  now: [reading],
  next: [
    {
      entry: pile,
      score: 1.4,
      reasons: [
        { signal: "creator", text: "You rate Brandon Sanderson 8.5 across 4" },
      ],
    },
  ],
  year: {
    year: 2026,
    months,
    goals: [
      { item_type: "book", period: "month", count: 2, target: 24, done: 1 },
    ],
  },
  domains: [
    {
      item_type: "book",
      count: 105,
      status_counts: { read: 57, reading: 1, to_read: 41 },
      scores: [0, 1, 1, 2, 6, 8, 5, 3, 1, 1],
      mean_score: 6.1,
      covers: [],
      without_cover: 11,
    },
    {
      item_type: "anime",
      count: 81,
      status_counts: { watching: 1, completed: 74, plan_to_watch: 6 },
      scores: [0, 0, 0, 1, 3, 8, 20, 25, 10, 4],
      mean_score: 6.3,
      covers: [],
      without_cover: 0,
    },
  ],
  lately: [
    {
      kind: "finished",
      at: "2026-11-06",
      entry: entry(21, "Pálido fuego", "book", { status: "read", score: 7 }),
      score: 7,
      previous: null,
      count: 1,
    },
    {
      kind: "added",
      at: "2026-11-02T10:00:00Z",
      entry: entry(22, "Why Nations Fail", "book", { status: "to_read" }),
      score: null,
      previous: null,
      count: 1,
    },
  ],
  tidy: {
    duplicates: 12,
    without_cover: 32,
    unscored: 3,
    unscored_by_type: { book: 3 },
  },
  question: {
    kind: "revisit",
    entry: entry(23, "Pet Sematary", "book", { status: "read", score: 9 }),
    scored_at: "2019-03-02T00:00:00Z",
  },
  shelves: [
    { id: 1, name: "novela", slug: "novela", entry_count: 11 },
    { id: 2, name: "distopía", slug: "distopia", entry_count: 5 },
  ],
  lent: {
    total: 1,
    loans: [
      {
        id: 1,
        person: "Ana",
        lent_on: "2026-01-05",
        entry: entry(24, "Rayuela", "book", { status: "read" }),
      },
    ],
  },
};

// The front's layout: the two bands, movable and removable since Sprint 150
// (DEC-195), then the showcases.
const bands = ["now", "lately"];
const defaults = [
  ["now", "L"],
  ["lately", "L"],
  ["next", "L"],
  ["question", "S"],
  ["suggested", "M"],
].map(([module, size]) => ({ module, size, hidden: false }));

type Layout = typeof defaults;

/** A layout endpoint that keeps what is put, as the server does, across reloads. */
async function stubLayout(page: Page) {
  const store: { modules: Layout; puts: Layout[] } = {
    modules: defaults,
    puts: [],
  };
  await page.route("**/api/home/layout", async (route) => {
    if (route.request().method() === "PUT") {
      const { modules } = route.request().postDataJSON() as {
        modules: Layout;
      };
      store.modules = modules;
      store.puts.push(modules);
    }
    await route.fulfill({ json: { modules: store.modules, defaults } });
  });
  return store;
}

async function stubHome(page: Page) {
  const patches: Array<{ id: string; body: Record<string, unknown> }> = [];
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: types }),
  );
  await page.route(isHome, (route) => route.fulfill({ json: home }));
  // What Personalize's add dialog draws before something is placed (Sprint 150).
  await page.route("**/api/home/preview?**", (route) =>
    route.fulfill({ json: home }),
  );
  await page.route("**/api/entries/*", async (route) => {
    const request = route.request();
    if (request.method() !== "PATCH") return route.fallback();
    const id = new URL(request.url()).pathname.split("/").pop()!;
    const body = request.postDataJSON() as Record<string, unknown>;
    patches.push({ id, body });
    const source = id === "10" ? pile : reading;
    await route.fulfill({ json: { ...source, ...body } });
  });
  return patches;
}

test("the Library opens with the greeting, what is under way, lately and the showcases, above the grid", async ({
  page,
}) => {
  await stubHome(page);
  await stubLayout(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      level: 2,
      name: "Sunday. Day 32 of Designing Data-Intensive Applications.",
    }),
  ).toBeVisible();
  for (const name of ["On now", "Lately", "Up next", "One question"]) {
    await expect(page.getByRole("region", { name })).toBeVisible();
  }
  // It is the Library's page: its own field above, the whole library below.
  await expect(page.getByRole("searchbox")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Everything" })).toBeVisible();
});

test("a search puts the front away: it is a question the front does not answer", async ({
  page,
}) => {
  await stubHome(page);
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Lately" })).toBeVisible();
  await page.getByRole("searchbox").fill("seeded");
  await expect(page.getByRole("region", { name: "Lately" })).toHaveCount(0);
});

test("the pile's count opens the pile as a list, and Sort the deck (DEC-192)", async ({
  page,
}) => {
  await stubHome(page);
  await page.route("**/api/pile?*", (route) =>
    route.fulfill({ json: home.next }),
  );
  await page.goto("/");
  const next = page.getByRole("region", { name: "Up next" });
  await expect(next.getByRole("link", { name: "Sort" })).toHaveAttribute(
    "href",
    "/deck/planned",
  );
  await next.getByRole("link", { name: /on the pile/ }).click();
  await expect(page).toHaveURL(/\/pile$/);
  await expect(page.getByRole("heading", { name: "The pile" })).toBeVisible();
  await expect(page.getByRole("list").getByRole("listitem")).toHaveCount(
    home.next.length,
  );
});

/** The showcases in the stored order, the bands aside. */
const showcases = (modules: Layout) =>
  modules.map((row) => row.module).filter((module) => !bands.includes(module));

test("Personalize reorders with the keyboard, resizes and removes in place, adds from the plus, and a reload keeps it", async ({
  page,
}) => {
  await stubHome(page);
  const store = await stubLayout(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Personalize" }).click();
  const bar = page.getByRole("toolbar", { name: "Personalize" });
  await expect(bar).toBeVisible();
  // In place, and nothing in the page but what is placed and one plus (DEC-195).
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("radiogroup", { name: "Theme" })).toHaveCount(0);

  await page
    .getByRole("button", { name: "Move One question", exact: true })
    .focus();
  await page.keyboard.press("ArrowLeft");
  await expect(
    page.getByRole("button", { name: "Move One question", exact: true }),
  ).toBeFocused();
  await page
    .getByRole("group", { name: "Size of One question" })
    .getByRole("button", { name: "Large" })
    .click();
  await page.getByRole("button", { name: "Remove Up next" }).click();
  await page.getByRole("button", { name: "Remove Lately" }).click();
  await expect(page.getByRole("region", { name: "Lately" })).toHaveCount(0);

  // The plus offers what was removed, with a preview, and adds it back.
  await page
    .getByRole("button", { name: "Add to your library's front" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Add to your library" });
  await dialog.getByRole("radio", { name: "Lately" }).click();
  await expect(
    dialog.getByRole("region", { name: "Preview of Lately" }),
  ).toContainText("Lately");
  await expect(dialog.getByRole("radio", { name: "Up next" })).toBeVisible();
  await dialog.getByRole("button", { name: "Add Lately" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("region", { name: "Lately" })).toBeVisible();

  await bar.getByRole("button", { name: "Done" }).click();
  await expect(bar).toHaveCount(0);
  await expect
    .poll(() => showcases(store.modules).slice(0, 2))
    .toEqual(["question", "next"]);
  expect(store.modules.find((row) => row.module === "question")?.size).toBe(
    "L",
  );
  expect(store.modules.find((row) => row.module === "next")?.hidden).toBe(true);
  expect(store.modules.find((row) => row.module === "lately")?.hidden).toBe(
    false,
  );

  await page.reload();
  await expect(
    page.getByRole("region", { name: "One question" }),
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Up next" })).toHaveCount(0);

  await page.getByRole("button", { name: "Personalize" }).click();
  await page.getByRole("button", { name: "Reset" }).click();
  await expect.poll(() => store.modules).toEqual(defaults);
});

test("Personalize reorders by dragging a handle", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await stubHome(page);
  const store = await stubLayout(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Personalize" }).click();
  const handle = page.getByRole("button", {
    name: "Move One question",
    exact: true,
  });
  await handle.scrollIntoViewIfNeeded();
  await handle.hover();
  const to = (await page.locator('[data-module="next"]').boundingBox())!;
  await page.mouse.down();
  await page.mouse.move(to.x + 10, to.y + to.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect
    .poll(() => showcases(store.modules).slice(0, 2))
    .toEqual(["question", "next"]);
});

test("Start moves a pile entry under way", async ({ page }) => {
  const patches = await stubHome(page);
  await page.goto("/");
  // Sprint 132: each pick carries the ranking's strongest reason under it.
  await expect(
    page
      .getByRole("region", { name: "Up next" })
      .getByText("You rate Brandon Sanderson 8.5 across 4"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Start Mistborn" }).click();
  await expect
    .poll(() => patches)
    .toEqual([{ id: "10", body: { status: "reading" } }]);
});

test("Mark as read opens the finish sheet and finishes the entry", async ({
  page,
}) => {
  const patches = await stubHome(page);
  await page.goto("/");
  await page
    .getByRole("button", {
      name: "Mark Designing Data-Intensive Applications as read",
    })
    .click();
  const sheet = page.getByRole("dialog");
  await expect(sheet).toContainText(
    "You finished Designing Data-Intensive Applications",
  );
  await sheet.getByRole("button", { name: "Finish", exact: true }).click();
  await expect
    .poll(() => patches.map((patch) => patch.body.status))
    .toContain("read");
  await expect(sheet).toBeHidden();
});

test("the old /library address lands on / with its filters", async ({
  page,
}) => {
  await stubHome(page);
  await page.goto("/library?type=anime&sort=title");
  await expect(page).toHaveURL(/\/\?type=anime&sort=title/);
});

for (const theme of ["ink", "paper"] as const) {
  for (const width of [390, 1440]) {
    test(`Home has no horizontal scroll and no serious axe violations at ${width}px in ${theme}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript(
        (value) => localStorage.setItem("akasha:theme", value),
        theme,
      );
      await stubHome(page);
      await page.goto("/");
      await expect(page.getByRole("region", { name: "On now" })).toBeVisible();
      if (width === 390) {
        // Every module is the full width of the page at 390px, whatever its size.
        const widths = await page
          .locator("[data-module]")
          .evaluateAll((nodes) =>
            nodes.map((node) => Math.round(node.getBoundingClientRect().width)),
          );
        expect(new Set(widths).size).toBe(1);
      }
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      );
      expect(overflow).toBe(0);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      const serious = results.violations.filter(
        (violation) =>
          violation.impact === "serious" || violation.impact === "critical",
      );
      expect(
        serious.map(
          (v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`,
        ),
      ).toEqual([]);
    });
  }
}

for (const width of [390, 1440]) {
  test(`personalizing has no serious axe violations and no overflow at ${width}px, with and without the add dialog`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await stubHome(page);
    await stubLayout(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Personalize" }).click();
    await expect(
      page.getByRole("toolbar", { name: "Personalize" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      ),
    ).toBe(0);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const serious = results.violations.filter(
      (violation) =>
        violation.impact === "serious" || violation.impact === "critical",
    );
    expect(
      serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`),
    ).toEqual([]);

    // And with the add dialog open on a preview.
    await page.getByRole("button", { name: "Remove Lately" }).click();
    await page
      .getByRole("button", { name: "Add to your library's front" })
      .click();
    const dialog = page.getByRole("dialog", { name: "Add to your library" });
    await expect(
      dialog.getByRole("region", { name: "Preview of Lately" }),
    ).toContainText("Lately");
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            document
              .querySelector('[role="dialog"]')
              ?.getAnimations({ subtree: true }).length ?? 0,
        ),
      )
      .toBe(0);
    const open = await new AxeBuilder({ page })
      .include('[role="dialog"]')
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(
      open.violations
        .filter((v) => v.impact === "serious" || v.impact === "critical")
        .map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`),
    ).toEqual([]);
  });
}

const familyHome = {
  ...home,
  library_years: [
    {
      item_type: "book",
      year: 2026,
      total: 2,
      goal: {
        item_type: "book",
        period: "year",
        count: 12,
        target: 12,
        done: 2,
      },
      covers: [
        {
          entry_id: 24,
          item_id: 24,
          item_type: "book",
          title: "Rayuela",
          cover_url: null,
          score: 9,
        },
        {
          entry_id: 25,
          item_id: 25,
          item_type: "book",
          title: "Ficciones",
          cover_url: null,
          score: 8,
        },
      ],
    },
    {
      item_type: "anime",
      year: 2026,
      total: 1,
      goal: null,
      covers: [
        {
          entry_id: 26,
          item_id: 26,
          item_type: "anime",
          title: "Seven Samurai",
          cover_url: null,
          score: 10,
        },
      ],
    },
  ],
  shelf_modules: [
    {
      id: 3,
      name: "Favorites",
      slug: "favorites",
      entry_count: 2,
      covers: [
        {
          entry_id: 24,
          item_id: 24,
          item_type: "book",
          title: "Rayuela",
          cover_url: null,
          score: 9,
        },
        {
          entry_id: 26,
          item_id: 26,
          item_type: "anime",
          title: "Seven Samurai",
          cover_url: null,
          score: 10,
        },
      ],
    },
  ],
};

const familyLayout = [
  ...defaults.slice(0, 4),
  { module: "year:book", size: "M", hidden: false, label: "Books this year" },
  { module: "year:anime", size: "M", hidden: false, label: "Anime this year" },
  { module: "shelf:3", size: "M", hidden: false, label: "Shelf: Favorites" },
  ...defaults.slice(4),
];

for (const width of [390, 1440]) {
  test(`a library's year and a shelf sit on Home at ${width}px (DEC-192)`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await stubHome(page);
    await page.route(isHome, (route) => route.fulfill({ json: familyHome }));
    await page.route("**/api/home/layout", (route) =>
      route.fulfill({
        json: { modules: familyLayout, defaults: familyLayout },
      }),
    );
    await page.goto("/");
    const books = page.getByRole("region", { name: "Your 2026 books" });
    await expect(books).toBeVisible();
    await expect(
      books.getByRole("list", { name: "2 of 12 books in 2026" }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Your 2026 anime" }),
    ).toBeVisible();
    const shelf = page.getByRole("region", { name: "Favorites" });
    await expect(
      shelf.getByRole("link", { name: "2 on the shelf →" }),
    ).toHaveAttribute("href", "/shelves/favorites");
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBe(0);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(
      results.violations
        .filter((v) => v.impact === "serious" || v.impact === "critical")
        .map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`),
    ).toEqual([]);
  });
}

test("an empty library draws no front, only its own first screen", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("Your library is waiting")).toBeVisible();
  await expect(page.getByRole("region", { name: "Lately" })).toHaveCount(0);
});
