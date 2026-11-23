import AxeBuilder from "@axe-core/playwright";
import { type Page } from "@playwright/test";

import { expect, test } from "./console";
import { entry as seededEntry } from "./seed";

/**
 * Home (Sprints 130-131, DEC-183): the screen Akasha opens on. Renders from one
 * `GET /api/home`; *Start* and *Finished* change the entry; a library tile opens
 * the filtered library; *Edit home* reorders (keys and drag), resizes and hides
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
      reason: "creator",
      creator: "Brandon Sanderson",
      mean_score: 8.5,
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

const defaults = [
  ["now", "M"],
  ["next", "L"],
  ["year", "L"],
  ["lately", "M"],
  ["libraries", "L"],
  ["tidy", "S"],
  ["question", "S"],
  ["shelves", "S"],
  ["lent", "S"],
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

/** The modules on screen, in order, by their `data-module`. */
function shown(page: Page) {
  return page
    .locator("[data-module]")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-module")),
    );
}

async function stubHome(page: Page) {
  const patches: Array<{ id: string; body: Record<string, unknown> }> = [];
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: types }),
  );
  await page.route("**/api/home", (route) => route.fulfill({ json: home }));
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

test("Home renders its modules from the one payload", async ({ page }) => {
  await stubHome(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Sunday. Day 32 of Designing Data-Intensive Applications.",
  );
  for (const name of [
    "On now",
    "Up next",
    "2026",
    "Lately",
    "Your libraries",
    "Tidy up",
    "One question",
    "Shelves",
    "Lent out",
  ]) {
    await expect(page.getByRole("region", { name })).toBeVisible();
  }
  await expect(page.getByText("1 / 24")).toBeVisible();
});

test("the year and Lately share a row, 7 and 5", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await stubHome(page);
  await page.goto("/");
  const year = await page.locator('[data-module="year"]').boundingBox();
  const lately = await page.locator('[data-module="lately"]').boundingBox();
  expect(year && lately).toBeTruthy();
  expect(Math.abs(year!.y - lately!.y)).toBeLessThan(2);
  expect(year!.width / lately!.width).toBeCloseTo(7 / 5, 0);
});

test("Tidy up's counts open what resolves them", async ({ page }) => {
  await stubHome(page);
  await page.goto("/");
  const tidy = page.getByRole("region", { name: "Tidy up" });
  await tidy.getByRole("link", { name: /finished, not scored/ }).click();
  await expect(page).toHaveURL(
    /\/library\?type=book&status=read&unscored=true/,
  );
  await expect(
    page.getByRole("button", { name: /No score yet/ }),
  ).toBeVisible();
});

test("Edit home reorders with the keyboard, resizes and hides, and a reload keeps it", async ({
  page,
}) => {
  await stubHome(page);
  const store = await stubLayout(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Edit home" }).click();
  const panel = page.getByRole("dialog", { name: "Edit home" });
  await panel.getByRole("button", { name: "Move Lately" }).focus();
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("ArrowUp");
  await expect(
    panel.getByRole("button", { name: "Move Lately" }),
  ).toBeFocused();
  await panel
    .getByRole("group", { name: "Size of Lately" })
    .getByRole("button", { name: "Small" })
    .click();
  await panel.getByRole("switch", { name: "Show Lent out" }).click();
  await panel.getByRole("button", { name: "Done" }).click();
  await expect(panel).toBeHidden();
  await expect
    .poll(() => store.modules.map((row) => row.module).slice(0, 3))
    .toEqual(["now", "lately", "next"]);
  expect(store.modules.find((row) => row.module === "lately")?.size).toBe("S");
  expect(store.modules.find((row) => row.module === "lent")?.hidden).toBe(true);

  await page.reload();
  await expect(page.getByRole("region", { name: "Lately" })).toBeVisible();
  expect((await shown(page)).slice(0, 3)).toEqual(["now", "lately", "next"]);
  await expect(page.getByRole("region", { name: "Lent out" })).toHaveCount(0);

  await page.getByRole("button", { name: "Edit home" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Reset" }).click();
  await expect.poll(() => store.modules).toEqual(defaults);
});

test("Edit home reorders by dragging a handle", async ({ page }) => {
  await stubHome(page);
  const store = await stubLayout(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Edit home" }).click();
  const panel = page.getByRole("dialog", { name: "Edit home" });
  const handle = panel.getByRole("button", { name: "Move Shelves" });
  // The panel zooms in; hovering waits for the handle to stand still.
  await handle.hover();
  const from = (await handle.boundingBox())!;
  const to = (await panel.locator('[data-module="next"]').boundingBox())!;
  await page.mouse.down();
  await page.mouse.move(from.x + from.width / 2, to.y + 2, { steps: 8 });
  await page.mouse.up();
  await expect
    .poll(() => store.modules.map((row) => row.module).slice(0, 3))
    .toEqual(["now", "shelves", "next"]);
});

test("Start moves a pile entry under way", async ({ page }) => {
  const patches = await stubHome(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start Mistborn" }).click();
  await expect
    .poll(() => patches)
    .toEqual([{ id: "10", body: { status: "reading" } }]);
});

test("Finished opens the finish sheet and finishes the entry", async ({
  page,
}) => {
  const patches = await stubHome(page);
  await page.goto("/");
  await page
    .getByRole("button", {
      name: "Finished Designing Data-Intensive Applications",
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

test("a library tile opens the library filtered to its domain", async ({
  page,
}) => {
  await stubHome(page);
  await page.goto("/");
  await page.getByRole("link", { name: /^81 Anime/ }).click();
  await expect(page).toHaveURL(/\/library\?type=anime/);
});

test("a / address with library filters lands on the library", async ({
  page,
}) => {
  await stubHome(page);
  await page.goto("/?type=anime&sort=title");
  await expect(page).toHaveURL(/\/library\?type=anime&sort=title/);
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
  test(`Edit home has no serious axe violations at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await stubHome(page);
    await stubLayout(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Edit home" }).click();
    await expect(page.getByRole("dialog", { name: "Edit home" })).toBeVisible();
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
  });
}

test("an empty library gets the first-run message", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your desk is ready" }),
  ).toBeVisible();
});
