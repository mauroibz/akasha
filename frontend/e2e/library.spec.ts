import { expect, test, type Page } from "@playwright/test";

import {
  animatedSurfaces,
  expectAnimated,
  expectStill,
  sampleAnimations,
} from "./motion";
import { chooseOption, expectSelected } from "./radix";

const pixelCover =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

const longTitle =
  "A Ludicrously Long Title About The Consequences Of Unbounded Metadata In Virtualized Grids And Their Discontents";
const longAuthor =
  "Vandermeer-Vandermeer de la Fuente y Castellanos de Aragón, María Purificación";

function entry(id: number) {
  return {
    id,
    item_id: id,
    status: "read",
    score: (id % 10) + 1,
    notes: null,
    date_added: "2026-07-22T00:00:00Z",
    date_started: null,
    date_finished: null,
    reread_count: 0,
    score_provisional: id % 3 === 0,
    suggested_status: null,
    item: {
      id,
      type: "book",
      // The first two entries carry deliberately hostile metadata so layout
      // assertions cover long titles/authors, and every other entry carries a
      // real cover so both populated and empty covers are exercised.
      title:
        id <= 2
          ? `${longTitle} ${String(id).padStart(4, "0")}`
          : `Seeded book ${String(id).padStart(4, "0")}`,
      subtitle: null,
      year: 1900 + (id % 126),
      sort_author: id <= 2 ? longAuthor : `Author ${id % 200}`,
      cover_url: id % 2 === 0 ? pixelCover : null,
      cover_path: null,
      metadata: {},
      identifiers: {},
      sources: [],
    },
    shelves: [],
  };
}

async function seedLibrary(page: Page) {
  const items = Array.from({ length: 5000 }, (_, index) => entry(index + 1));
  await page.route("**/api/entries?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items,
        next_cursor: null,
        total: 5000,
        facets: { status_counts: { read: 5000, unsorted: 27 } },
      }),
    });
  });
}

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Overlap with a 1px tolerance for sub-pixel layout rounding. */
function overlaps(a: Box, b: Box): boolean {
  return (
    a.x < b.x + b.width - 1 &&
    b.x < a.x + a.width - 1 &&
    a.y < b.y + b.height - 1 &&
    b.y < a.y + a.height - 1
  );
}

function contains(outer: Box, inner: Box): boolean {
  return (
    inner.x >= outer.x - 1 &&
    inner.y >= outer.y - 1 &&
    inner.x + inner.width <= outer.x + outer.width + 1 &&
    inner.y + inner.height <= outer.y + outer.height + 1
  );
}

function describeBox(label: string, box: Box): string {
  return `${label} x=${box.x.toFixed(1)} y=${box.y.toFixed(1)} w=${box.width.toFixed(1)} h=${box.height.toFixed(1)}`;
}

/** Bounding boxes of every mounted card and its three layout regions. */
async function readCards(page: Page) {
  return page.evaluate(() => {
    const rect = (element: Element | null) => {
      if (!element) return null;
      const { x, y, width, height } = element.getBoundingClientRect();
      return { x, y, width, height };
    };
    return Array.from(document.querySelectorAll("[data-entry-id]")).map(
      (card) => ({
        id: card.getAttribute("data-entry-id") ?? "",
        card: rect(card)!,
        cover: rect(card.querySelector("[data-card-cover]")),
        meta: rect(card.querySelector("[data-card-meta]")),
        controls: rect(card.querySelector("[data-card-controls]")),
      }),
    );
  });
}

async function libraryBox(page: Page): Promise<Box> {
  const box = await page.getByRole("feed", { name: "Library" }).boundingBox();
  expect(box).not.toBeNull();
  return box!;
}

const viewports = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 900 },
];

test("the deterministic 5,000-entry library mounts only overscanned rows", async ({
  page,
}) => {
  await seedLibrary(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Seeded book 0003" }),
  ).toBeVisible();
  const library = page.getByRole("feed", { name: "Library" });
  expect(Number(await library.getAttribute("data-mounted-count"))).toBeLessThan(
    20,
  );
  await library.evaluate((element) => {
    element.scrollTop = 250_000;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect
    .poll(async () => Number(await library.getAttribute("data-mounted-count")))
    .toBeLessThan(20);
  // A multi-column grid mounts `columns` cards per virtual row; the DOM budget
  // is therefore expressed per card as well as per row.
  const mountedCards = await page.locator("[data-entry-id]").count();
  const mountedRows = Number(await library.getAttribute("data-mounted-count"));
  // Reported so a future sprint can see how much headroom is left rather than
  // discovering the bound only when it is breached. Adopting shadcn primitives
  // in Sprint 015 added DOM nodes per card but no cards or rows.
  console.log(
    `mounted rows=${mountedRows} cards=${mountedCards} (DEC-023 bounds: <20 rows, <48 cards)`,
  );
  expect(mountedCards).toBeLessThan(48);
});

test("changing sort crossfades the container and animates no row", async ({
  page,
}) => {
  await seedLibrary(page);
  await page.goto("/");
  await expect(page.locator("[data-entry-id='1']")).toBeVisible();
  // Stamp the live container so a second one can be told from a re-rendered
  // first one: exactly one re-key must happen, not zero and not two.
  await page
    .locator("[data-library-container]")
    .evaluate((element) => element.setAttribute("data-probe", "before"));

  const samples = await sampleAnimations(page, async () => {
    await chooseOption(
      page,
      page.getByRole("combobox", { name: "Sort library" }),
      "Score ↓",
    );
    await expect(page.locator("[data-library-container]")).not.toHaveAttribute(
      "data-probe",
      "before",
    );
    await expect(page.locator("[data-entry-id='1']")).toBeVisible();
  });

  // Technical spec section 8: rows do not use layout animations. Not "should
  // not" -- the sampler watched every frame of the transition and would have
  // caught one.
  const rowLevel = samples.filter(
    (sample) => sample.target === "card" || sample.target === "row",
  );
  expect(rowLevel, JSON.stringify(rowLevel.slice(0, 5))).toEqual([]);
  expect(samples.some((sample) => sample.target === "container")).toBe(true);
  await expect(page.locator("[data-library-container]")).toHaveCount(1);
});

test("the mounted-DOM budget holds through a crossfade", async ({ page }) => {
  await seedLibrary(page);
  await page.goto("/");
  await expect(page.locator("[data-entry-id='1']")).toBeVisible();
  await page.evaluate(() => {
    const peak = { cards: 0, rows: 0, containers: 0 };
    const tick = () => {
      peak.cards = Math.max(
        peak.cards,
        document.querySelectorAll("[data-entry-id]").length,
      );
      peak.rows = Math.max(
        peak.rows,
        document.querySelectorAll("[data-virtual-row]").length,
      );
      peak.containers = Math.max(
        peak.containers,
        document.querySelectorAll("[data-library-container]").length,
      );
      handle = requestAnimationFrame(tick);
    };
    let handle = requestAnimationFrame(tick);
    Object.assign(window, {
      __peak: peak,
      __peakStop: () => cancelAnimationFrame(handle),
    });
  });
  await chooseOption(
    page,
    page.getByRole("combobox", { name: "Sort library" }),
    "Title ↓",
  );
  await expect(page.locator("[data-entry-id='1']")).toBeVisible();
  const peak = await page.evaluate(() => {
    const store = window as unknown as {
      __peak: { cards: number; rows: number; containers: number };
      __peakStop: () => void;
    };
    store.__peakStop();
    return store.__peak;
  });
  console.log(
    `crossfade peak rows=${peak.rows} cards=${peak.cards} containers=${peak.containers} (DEC-023 bounds: <20 rows, <48 cards)`,
  );
  // The whole reason the crossfade waits for the outgoing list to leave: two
  // simultaneous virtualized stacks would breach both bounds at once.
  expect(peak.containers).toBe(1);
  expect(peak.rows).toBeLessThan(20);
  expect(peak.cards).toBeLessThan(48);
});

test("animated surfaces really do animate without the preference", async ({
  page,
}) => {
  await seedLibrary(page);
  await page.goto("/");
  await expect(page.locator("[data-entry-id='1']")).toBeVisible();
  await expectAnimated(page, animatedSurfaces.card, "card");
  await expectAnimated(page, animatedSurfaces.cover, "cover");
  await expectAnimated(page, animatedSurfaces.scoreTrigger, "score trigger");
});

test("reduced motion reaches the animations no stylesheet can touch", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await seedLibrary(page);
  await page.goto("/");
  await expect(page.locator("[data-entry-id='1']")).toBeVisible();

  // The `*` block in index.css cannot help here. Motion drives the Web
  // Animations API and inline styles, which no stylesheet overrides -- which is
  // the entire reason the preset layer reads the preference in JavaScript.
  const samples = await sampleAnimations(page, async () => {
    await chooseOption(
      page,
      page.getByRole("combobox", { name: "Sort library" }),
      "Score ↓",
    );
    await expect(page.locator("[data-entry-id='1']")).toBeVisible();
    await page.locator("[data-entry-id='1'] [data-provisional]").click();
    await page.getByRole("button", { name: "Score 4" }).click();
  });
  const moving = samples.filter((sample) => sample.duration > 0.01);
  expect(moving, JSON.stringify(moving.slice(0, 5))).toEqual([]);

  const stillRunning = await page.evaluate(() =>
    document
      .getAnimations()
      .map((animation) => Number(animation.effect?.getTiming().duration ?? 0)),
  );
  expect(stillRunning.every((duration) => duration <= 0.01)).toBe(true);
});

test("a cover that arrives late shifts nothing in its card", async ({
  page,
}) => {
  await seedLibrary(page);
  // Every even entry asks for this cover; it is held back so the card can be
  // measured while the image is genuinely still in flight.
  await page.route("**/covers/late.png", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700));
    await route.fulfill({
      contentType: "image/png",
      body: Buffer.from(pixelCover.split(",")[1], "base64"),
    });
  });
  await page.route("**/api/entries?**", async (route) => {
    const items = Array.from({ length: 60 }, (_, index) => {
      const row = entry(index + 1);
      return { ...row, item: { ...row.item, cover_url: "/covers/late.png" } };
    });
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items,
        next_cursor: null,
        total: 60,
        facets: { status_counts: { read: 60 } },
      }),
    });
  });
  await page.goto("/");

  const card = page.locator("[data-entry-id='1']");
  await expect(card.locator("img")).toHaveAttribute(
    "data-cover-state",
    "loading",
  );
  const before = {
    card: await card.boundingBox(),
    cover: await card.locator("[data-card-cover]").boundingBox(),
    meta: await card.locator("[data-card-meta]").boundingBox(),
  };

  await expect(card.locator("img")).toHaveAttribute(
    "data-cover-state",
    "loaded",
    { timeout: 5000 },
  );
  const after = {
    card: await card.boundingBox(),
    cover: await card.locator("[data-card-cover]").boundingBox(),
    meta: await card.locator("[data-card-meta]").boundingBox(),
  };

  for (const region of ["card", "cover", "meta"] as const) {
    const a = before[region]!;
    const b = after[region]!;
    expect(
      Math.abs(a.x - b.x) +
        Math.abs(a.y - b.y) +
        Math.abs(a.width - b.width) +
        Math.abs(a.height - b.height),
      `${describeBox(`${region} before`, a)} -> ${describeBox(`${region} after`, b)}`,
    ).toBeLessThanOrEqual(1);
  }
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});

test("keyboard guards and reduced motion remain effective", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await seedLibrary(page);
  await page.goto("/");
  await page.keyboard.press("/");
  await expect(
    page.getByRole("searchbox", { name: "Search library" }),
  ).toBeFocused();
  await page.keyboard.type("a");
  await expect(page).toHaveURL("/");
  await expect(
    page.getByRole("searchbox", { name: "Search library" }),
  ).toHaveValue("a");
  const firstRow = page.locator("[data-entry-id='1']");
  await firstRow.focus();
  await page.keyboard.press("j");
  await expect(page.locator("[data-entry-id='2']")).toBeFocused();

  // Sampling one element's transition duration is what made this assertion
  // vacuous for three sprints: `article` carried no transition at all, so it
  // was true of a page with no animation in it. Every surface this sprint
  // animates is checked now, on both properties, including one that Radix
  // portals out of the card entirely.
  await expectStill(page, animatedSurfaces.card, "card");
  await expectStill(page, animatedSurfaces.container, "library container");
  await expectStill(page, animatedSurfaces.cover, "cover");
  await expectStill(page, animatedSurfaces.scoreTrigger, "score trigger");

  const card = page.locator("[data-entry-id='1']");
  await card.locator("[data-provisional]").click();
  await expectStill(page, "[data-score-panel]", "score panel");
  await page.keyboard.press("Escape");

  await card.getByRole("combobox").click();
  await expectStill(page, "[role='listbox']", "portalled status listbox");
  await page.keyboard.press("Escape");
  await page.getByRole("heading", { name: "Akasha" }).click();
  await page.keyboard.press("a");
  await expect(page).toHaveURL("/add");
});

for (const viewport of viewports) {
  test(`grid cards keep cover, metadata and controls separated at ${viewport.name} width`, async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });
    await seedLibrary(page);
    await page.goto("/");
    await expect(page.locator("[data-entry-id='1']")).toBeVisible();

    const library = await libraryBox(page);
    const cards = await readCards(page);
    expect(cards.length).toBeGreaterThan(1);

    for (const card of cards) {
      expect(card.cover, `entry ${card.id} has no cover region`).not.toBeNull();
      expect(
        card.meta,
        `entry ${card.id} has no metadata region`,
      ).not.toBeNull();
      expect(
        card.controls,
        `entry ${card.id} has no controls region`,
      ).not.toBeNull();

      // A cover is the primary visual element; a zero-width cover is the
      // diagnosed collapse of the cover into the metadata column.
      expect(
        card.cover!.width,
        `entry ${card.id} cover width`,
      ).toBeGreaterThanOrEqual(48);
      expect(
        card.cover!.height,
        `entry ${card.id} cover height`,
      ).toBeGreaterThanOrEqual(72);

      for (const [a, b] of [
        ["cover", "meta"],
        ["cover", "controls"],
        ["meta", "controls"],
      ] as const) {
        expect(
          overlaps(card[a]!, card[b]!),
          `entry ${card.id}: ${describeBox(a, card[a]!)} overlaps ${describeBox(b, card[b]!)}`,
        ).toBe(false);
      }

      for (const region of ["cover", "meta", "controls"] as const) {
        expect(
          contains(card.card, card[region]!),
          `entry ${card.id}: ${describeBox(region, card[region]!)} escapes ${describeBox("card", card.card)}`,
        ).toBe(true);
      }

      expect(
        card.card.x >= library.x - 1 &&
          card.card.x + card.card.width <= library.x + library.width + 1,
        `entry ${card.id}: ${describeBox("card", card.card)} escapes ${describeBox("library", library)}`,
      ).toBe(true);
    }

    for (let i = 0; i < cards.length; i += 1)
      for (let j = i + 1; j < cards.length; j += 1)
        expect(
          overlaps(cards[i].card, cards[j].card),
          `entries ${cards[i].id} and ${cards[j].id} overlap`,
        ).toBe(false);

    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow, "horizontal page overflow").toBeLessThanOrEqual(1);
    expect(pageErrors).toEqual([]);
  });
}

test("an expanded score picker stays inside its card at every width", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await seedLibrary(page);

  for (const viewport of viewports) {
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });
    await page.goto("/");
    const card = page.locator("[data-entry-id='1']");
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: /^Score for /i }).click();
    const panel = page.locator("[data-score-panel]");
    await expect(panel).toBeVisible();
    await expect(panel.getByRole("button", { name: "Score 10" })).toBeVisible();

    const panelBox = (await panel.boundingBox())!;
    const cards = await readCards(page);
    const own = cards.find((row) => row.id === "1")!;
    expect(
      contains(own.card, panelBox),
      `${viewport.name}: ${describeBox("score panel", panelBox)} escapes ${describeBox("card", own.card)}`,
    ).toBe(true);
    for (const other of cards.filter((row) => row.id !== "1"))
      expect(
        overlaps(panelBox, other.card),
        `${viewport.name}: expanded score panel overlaps entry ${other.id}`,
      ).toBe(false);

    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(
      overflow,
      `${viewport.name} horizontal page overflow`,
    ).toBeLessThanOrEqual(1);
  }
  expect(pageErrors).toEqual([]);
});

test("a card status listbox is not recycled out from under the reader", async ({
  page,
}) => {
  // DEC-023 pins the card height for fixed-size virtualization, and a Radix
  // Select portals its listbox to document.body while the row that owns the
  // trigger can unmount on scroll. Sprint 015 flagged this as a risk to measure
  // rather than assume, and the measured answer is that Radix makes the rest of
  // the document inert while the listbox is open: pointer events are blocked
  // and scrolling is locked, so the virtualizer cannot recycle the owning row.
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.route("**/api/entries/*", async (route) => {
    const request = route.request();
    if (request.method() !== "PATCH") return route.fallback();
    const body = JSON.parse(request.postData() ?? "{}") as Record<
      string,
      unknown
    >;
    await route.fulfill({ json: { ...entry(1), ...body } });
  });
  await seedLibrary(page);
  await page.goto("/");

  const card = page.locator("[data-entry-id='1']");
  await expect(card).toBeVisible();
  // Addressed by class, not by role: while the listbox is open Radix marks the
  // rest of the document aria-hidden, so the feed role is deliberately absent
  // from the accessibility tree until it closes.
  const scroller = page.locator(".library-scroll");
  const box = (await scroller.boundingBox())!;
  const centre = { x: box.x + box.width / 2, y: box.y + box.height / 2 };

  await card.getByRole("combobox").click();
  const listbox = page.getByRole("listbox");
  await expect(listbox).toBeVisible();

  // A real scroll gesture over the list, which is what a reader would do.
  await page.mouse.move(centre.x, centre.y);
  await page.mouse.wheel(0, 4000);
  await expect(listbox).toBeVisible();
  await expect(card).toBeVisible();
  expect(await scroller.evaluate((node) => node.scrollTop)).toBe(0);

  await page.getByRole("option", { name: "Reading", exact: true }).click();
  await expect(listbox).toBeHidden();
  await expectSelected(card.getByRole("combobox"), "Reading");

  // Once it is closed the list scrolls normally again.
  await page.mouse.move(centre.x, centre.y);
  await page.mouse.wheel(0, 4000);
  await expect
    .poll(() => scroller.evaluate((node) => node.scrollTop))
    .toBeGreaterThan(0);
  expect(pageErrors).toEqual([]);
});

test("grid view is multi-column where space permits and reflows on resize", async ({
  page,
}) => {
  await seedLibrary(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.locator("[data-entry-id='1']")).toBeVisible();

  const columnsAt = async () => {
    const cards = await readCards(page);
    const topRow = Math.min(...cards.map((card) => card.card.y));
    return cards.filter((card) => Math.abs(card.card.y - topRow) < 2).length;
  };

  expect(await columnsAt(), "desktop columns").toBeGreaterThanOrEqual(2);

  await page.setViewportSize({ width: 375, height: 812 });
  await expect.poll(columnsAt, { message: "mobile columns" }).toBe(1);
  // Reflow must not leave stale virtual offsets behind.
  const cards = await readCards(page);
  for (let i = 0; i < cards.length; i += 1)
    for (let j = i + 1; j < cards.length; j += 1)
      expect(
        overlaps(cards[i].card, cards[j].card),
        `after resize, entries ${cards[i].id} and ${cards[j].id} overlap`,
      ).toBe(false);

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect
    .poll(columnsAt, { message: "restored desktop columns" })
    .toBeGreaterThanOrEqual(2);
});

test("grid and table views both keep inline editing, navigation and persistence", async ({
  page,
}) => {
  await page.route("**/api/entries/*", async (route) => {
    const request = route.request();
    if (request.method() !== "PATCH") return route.fallback();
    const body = JSON.parse(request.postData() ?? "{}") as Record<
      string,
      unknown
    >;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ ...entry(3), ...body, score_provisional: false }),
    });
  });
  await seedLibrary(page);
  await page.goto("/");

  const card = page.locator("[data-entry-id='3']");
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: /^Score for /i }).click();
  await page.getByRole("button", { name: "Score 4" }).click();
  await expect(
    card.getByRole("button", { name: /Score for .*: 4/i }),
  ).toBeVisible();

  await chooseOption(page, card.getByRole("combobox"), "Reading");
  await expectSelected(card.getByRole("combobox"), "Reading");

  await page.getByRole("button", { name: "Table view" }).click();
  await expect(page.getByRole("table", { name: "Library" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("table", { name: "Library" })).toBeVisible();

  await page.getByRole("button", { name: "Grid view" }).click();
  await expect(page.getByRole("feed", { name: "Library" })).toBeVisible();
  await page
    .locator("[data-entry-id='3']")
    .getByRole("button", { name: /^Open / })
    .click();
  await expect(page).toHaveURL(/\/books\/3$/);
});
