import type { Goal, GoalProgress } from "@/api/goals";
import type { ItemType } from "@/api/library";
import { spelled, type Segment } from "@/features/insights/prose";

/**
 * Gentle goals, drawn (Sprint 104, DEC-169; slots since Sprint 127): the one sentence,
 * the slots or the bar, and the goals offered. Pure, so all are tested without a screen.
 *
 * Nothing here says behind. An empty slot is room left, a month with fewer than the
 * goal is not marked, and a later month can hold more than the goal: the year counts
 * them together.
 */

const names = Array.from({ length: 12 }, (_, month) =>
  new Intl.DateTimeFormat("en", { month: "long" }).format(
    new Date(2026, month, 1),
  ),
);

export function monthName(index: number): string {
  return names[index];
}

const em = (text: string): Segment => ({ text, em: true });
const plain = (text: string): Segment => ({ text });
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** The one sentence beside the slots: the goal, then where this month stands. */
export function goalSentence(
  goal: Pick<Goal, "count" | "period">,
  progress: Pick<GoalProgress, "months" | "total" | "year">,
  today: Date,
): Segment[] {
  const current = progress.year === today.getFullYear();
  if (!current) {
    return [
      plain("You finished "),
      em(spelled(progress.total)),
      plain(
        ` in ${progress.year}, against ${spelled(goal.count)} a ${goal.period}.`,
      ),
    ];
  }
  if (goal.period === "year") {
    return [
      em(capital(spelled(goal.count))),
      plain(" this year, at your own pace. "),
      em(capital(spelled(progress.total))),
      plain(" so far."),
    ];
  }
  const month = today.getMonth();
  const now = progress.months[month] ?? 0;
  const parts: Segment[] = [
    em(capital(spelled(goal.count))),
    plain(" a month, at your own pace. "),
  ];
  if (now === 0) {
    parts.push(em(monthName(month)), plain(" is still open."));
  } else if (now >= goal.count) {
    parts.push(
      em(monthName(month)),
      plain(" has "),
      em(spelled(now)),
      plain(" already."),
    );
  } else {
    parts.push(
      em(monthName(month)),
      plain(" has "),
      em(spelled(now)),
      plain(" so far."),
    );
  }
  return parts;
}

/** The domains a goal can count: those that record a finish date. */
export function goalDomains(types: ItemType[]): ItemType[] {
  return types.filter((type) =>
    (type.entry_fields ?? []).includes("date_finished"),
  );
}

/** The most slots drawn; a larger goal is a bar (Sprint 127, mockup 3C). */
export const slotCap = 24;

const paces: Array<{ count: number; words: string }> = [
  { count: 6, words: "one every two months" },
  { count: 12, words: "one a month" },
  { count: 24, words: "two a month" },
  { count: 36, words: "three a month" },
  { count: 52, words: "one a week" },
];

/**
 * Three goals to offer when none is set (Sprint 127, DEC-179, mockup 3A): the first
 * three paces above what the year already holds, each said as a pace.
 */
export function suggestedCounts(
  done: number,
): Array<{ count: number; words: string }> {
  const above = paces.filter((pace) => pace.count > done);
  return (above.length >= 3 ? above : paces.slice(-3)).slice(0, 3);
}

export interface Slot<T> {
  entry: T | null;
  /** The first empty slot: where the next one goes. */
  next: boolean;
}

/**
 * The goal as slots (mockup 3B): one per thing aimed at, filled by the year's finishes
 * in the order they happened, every finish beyond the goal given one too. `null` above
 * `slotCap`, where the slots would be too small to read.
 */
export function slotsFor<T extends { date_finished: string | null }>(
  target: number,
  finished: T[],
): Slot<T>[] | null {
  if (target > slotCap) return null;
  const ordered = [...finished].sort((a, b) =>
    (a.date_finished ?? "").localeCompare(b.date_finished ?? ""),
  );
  const total = Math.max(target, ordered.length);
  return Array.from({ length: total }, (_, index) => ({
    entry: ordered[index] ?? null,
    next: index === ordered.length,
  }));
}

/** How much of `year` has passed by `today`, 0 to 1 (the bar's mark). */
export function yearPassed(year: number, today: Date): number {
  if (year < today.getFullYear()) return 1;
  if (year > today.getFullYear()) return 0;
  const start = new Date(year, 0, 1).getTime();
  const end = new Date(year + 1, 0, 1).getTime();
  return (today.getTime() - start) / (end - start);
}
