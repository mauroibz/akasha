/**
 * Home's default layout (Sprint 130): each module and its width in columns of 12.
 * Static until Sprint 131 makes it editable and stores it per person; the keys are
 * what that stored layout will name.
 */
export type ModuleKey = "now" | "next" | "year" | "libraries";

export const defaultLayout: ReadonlyArray<{ key: ModuleKey; span: Span }> = [
  { key: "now", span: 5 },
  { key: "next", span: 7 },
  { key: "year", span: 12 },
  { key: "libraries", span: 12 },
];

export type Span = 3 | 4 | 5 | 6 | 7 | 8 | 12;

/**
 * Written out in full so Tailwind sees each class. Below 720px every module is one
 * column, in the same order.
 */
export const spanClass: Record<Span, string> = {
  3: "min-[720px]:col-span-3",
  4: "min-[720px]:col-span-4",
  5: "min-[720px]:col-span-5",
  6: "min-[720px]:col-span-6",
  7: "min-[720px]:col-span-7",
  8: "min-[720px]:col-span-8",
  12: "min-[720px]:col-span-12",
};
