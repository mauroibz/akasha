import type { ModuleLayout, ModuleSize } from "@/api/home";

/**
 * Home's modules and how they share a row (Sprints 130-131, DEC-183). The layout
 * itself (order, size, hidden) is stored per person on the server; these are the
 * keys it names, what each is called in *Edit home*, and how sizes become columns.
 */
export const MODULES = [
  "now",
  "next",
  "year",
  "lately",
  "libraries",
  "tidy",
  "question",
  "shelves",
  "lent",
] as const;

export type ModuleKey = (typeof MODULES)[number];

export function isModuleKey(key: string): key is ModuleKey {
  return (MODULES as readonly string[]).includes(key);
}

export const moduleLabels: Record<ModuleKey, string> = {
  now: "On now",
  next: "Up next",
  year: "The year",
  lately: "Lately",
  libraries: "Library tiles",
  tidy: "Tidy up",
  question: "One question",
  shelves: "Shelves",
  lent: "Lent out",
};

/** Modules that always take the whole row; their size only changes how much they show. */
export const fullWidth: ReadonlySet<ModuleKey> = new Set(["libraries"]);

/**
 * The server's default, used only until the stored layout arrives or when it cannot
 * be read: `GET /api/home/layout` is the source of truth and carries its own.
 */
export const fallbackLayout: ModuleLayout[] = [
  { module: "now", size: "M", hidden: false },
  { module: "next", size: "L", hidden: false },
  { module: "year", size: "L", hidden: false },
  { module: "lately", size: "M", hidden: false },
  { module: "libraries", size: "L", hidden: false },
  { module: "tidy", size: "S", hidden: false },
  { module: "question", size: "S", hidden: false },
  { module: "shelves", size: "S", hidden: false },
  { module: "lent", size: "S", hidden: false },
];

/** Columns of twelve a size asks for on a wide screen (the proposal's S 3, M 5, L 7). */
export const sizeSpan: Record<ModuleSize, number> = { S: 3, M: 5, L: 7 };

/**
 * Lay modules into rows of twelve, in order. A module that does not fit starts the
 * next row, and the columns a row leaves over are shared out among its modules from
 * the last one back, so no row ends in a gap: a year with nothing beside it takes the
 * whole row, three small modules take four columns each.
 */
export function packRows(
  modules: ReadonlyArray<{ key: ModuleKey; size: ModuleSize }>,
): Array<{ key: ModuleKey; size: ModuleSize; span: number }> {
  const placed: Array<{ key: ModuleKey; size: ModuleSize; span: number }> = [];
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
