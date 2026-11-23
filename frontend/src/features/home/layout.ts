import type { ModuleLayout, ModuleSize } from "@/api/home";

/**
 * The Library's showcases and how they share a row (Sprints 130-131, DEC-183; on the
 * Library since Sprint 141, DEC-193). The layout itself (order, size, hidden) is
 * stored per person on the server; these are the keys it names, what each is called
 * when arranging, and how sizes become columns. What the Library's bands and tabs
 * say is not a showcase: what is under way, what happened lately, the libraries,
 * the shelves' names, the small jobs and the loans were modules of Home.
 */
export const MODULES = [
  "now",
  "lately",
  "next",
  "question",
  "suggested",
] as const;

/**
 * The two bands (Sprint 150, DEC-195): layout items like any other, so they can be
 * moved and removed, and always the whole row; their size is not the person's.
 */
export const fullWidth: ReadonlySet<string> = new Set(["now", "lately"]);

export type ModuleKey = (typeof MODULES)[number];

export function isModuleKey(key: string): key is ModuleKey {
  return (MODULES as readonly string[]).includes(key);
}

/**
 * A member of a module family (Sprint 138, DEC-192): a library's year,
 * `year:<item type>`, a shelf, `shelf:<shelf id>`, or since Sprint 142 a number from
 * the Journal, `insight:<item type>:<section>`. The server lists the members that
 * exist, each with its own label.
 */
export type FamilyKey =
  `year:${string}` | `shelf:${string}` | `insight:${string}`;
export type HomeKey = ModuleKey | FamilyKey;

export function isFamilyKey(key: string): key is FamilyKey {
  return /^(year|shelf|insight):.+/.test(key);
}

export function isHomeKey(key: string): key is HomeKey {
  return isModuleKey(key) || isFamilyKey(key);
}

/** `insight:<item type>:<section>` taken apart; `null` when it is not one. */
export function parseInsightKey(
  key: string,
): { type: string; section: string } | null {
  const match = /^insight:([^:]+):(.+)$/.exec(key);
  return match ? { type: match[1], section: match[2] } : null;
}

/** What a showcase is called while arranging: a family member's label from the server. */
export function labelOf(row: {
  module: string;
  label?: string | null;
}): string {
  if (isModuleKey(row.module)) return moduleLabels[row.module];
  return row.label ?? row.module;
}

export const moduleLabels: Record<ModuleKey, string> = {
  now: "On now",
  lately: "Lately",
  next: "Up next",
  question: "One question",
  suggested: "More like this",
};

/**
 * The server's default, used only until the stored layout arrives or when it cannot
 * be read: `GET /api/home/layout` is the source of truth and carries its own.
 */
export const fallbackLayout: ModuleLayout[] = [
  { module: "now", size: "L", hidden: false },
  { module: "lately", size: "L", hidden: false },
  { module: "next", size: "L", hidden: false },
  { module: "question", size: "S", hidden: true },
  { module: "suggested", size: "M", hidden: true },
];

/** Columns of twelve a size asks for on a wide screen (the proposal's S 3, M 5, L 7). */
export const sizeSpan: Record<ModuleSize, number> = { S: 3, M: 5, L: 7 };

/**
 * Lay modules into rows of twelve, in order. A module that does not fit starts the
 * next row, and the columns a row leaves over are shared out among its modules from
 * the last one back, so no row ends in a gap: a year with nothing beside it takes the
 * whole row, three small modules take four columns each.
 */
export function packRows<K extends string>(
  modules: ReadonlyArray<{ key: K; size: ModuleSize }>,
): Array<{ key: K; size: ModuleSize; span: number }> {
  const placed: Array<{ key: K; size: ModuleSize; span: number }> = [];
  let row: typeof placed = [];
  let used = 0;
  const close = () => {
    let left = 12 - used;
    let index = row.length - 1;
    while (left > 0) {
      row[index].span += 1;
      left -= 1;
      index = index === 0 ? row.length - 1 : index - 1;
    }
    placed.push(...row);
    row = [];
    used = 0;
  };
  for (const { key, size } of modules) {
    const span = fullWidth.has(key) ? 12 : sizeSpan[size];
    if (used + span > 12) close();
    row.push({ key, size, span });
    used += span;
  }
  if (row.length) close();
  return placed;
}

/**
 * Written out in full so Tailwind sees each class. Below 720px every module is one
 * column, in the same order.
 */
export const spanClass: Record<number, string> = {
  1: "min-[720px]:col-span-1",
  2: "min-[720px]:col-span-2",
  3: "min-[720px]:col-span-3",
  4: "min-[720px]:col-span-4",
  5: "min-[720px]:col-span-5",
  6: "min-[720px]:col-span-6",
  7: "min-[720px]:col-span-7",
  8: "min-[720px]:col-span-8",
  9: "min-[720px]:col-span-9",
  10: "min-[720px]:col-span-10",
  11: "min-[720px]:col-span-11",
  12: "min-[720px]:col-span-12",
};
