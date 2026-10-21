import type { Goal, GoalProgress } from "@/api/goals";
import type { ItemType } from "@/api/library";
import { spelled, type Segment } from "@/features/insights/prose";

/**
 * Gentle goals, drawn (Sprint 104, DEC-169): the calendar of lights and the one
 * sentence beside it. Pure, so both are tested without a screen.
 *
 * Nothing here says behind. A month with fewer than the goal is not marked, it is
 * simply less lit; a later month can hold more than the goal, and the year counts
 * them together.
 */

/** One place in a month's column: lit by a finished entry, or not. */
export type Place = "lit" | "open" | "now" | "ahead";

export interface CalendarMonth {
  index: number;
  /** One letter, for the column foot. */
  short: string;
  /** The month's name, for the column's accessible description. */
  name: string;
  places: Place[];
  /** Finished entries beyond what the column draws. */
  more: number;
  current: boolean;
}

/** The tallest a column is drawn; a busier month says "+N" instead. */
export const columnCap = 6;

const names = Array.from({ length: 12 }, (_, month) =>
  new Intl.DateTimeFormat("en", { month: "long" }).format(
    new Date(2026, month, 1),
  ),
);

export function monthName(index: number): string {
  return names[index];
}

/**
 * The calendar's columns. A monthly goal draws that many places a month; a lit
 * place for each entry finished in it, beyond the goal too. A yearly goal has no
 * per-month share, so its columns hold only what was finished. Places in the
 * current month are `now`, later ones `ahead`; a past year has no `now`.
 */
export function calendarPlaces(
  months: number[],
  goal: Pick<Goal, "count" | "period"> | null,
  year: number,
  today: Date,
): CalendarMonth[] {
  const thisYear = today.getFullYear();
  const currentMonth =
    year === thisYear ? today.getMonth() : year < thisYear ? 12 : -1;
  const perMonth = goal?.period === "month" ? goal.count : 0;
  return months.map((finished, index) => {
    const total = Math.max(perMonth, finished);
    const drawn = Math.min(total, columnCap);
    const places: Place[] = Array.from({ length: drawn }, (_, slot) => {
      if (slot < finished) return "lit";
      if (index < currentMonth) return "open";
      if (index === currentMonth) return "now";
      return "ahead";
    });
    return {
      index,
      short: names[index][0],
      name: names[index],
      places,
      more: Math.max(0, finished - columnCap),
      current: index === currentMonth,
    };
  });
}

const em = (text: string): Segment => ({ text, em: true });
const plain = (text: string): Segment => ({ text });
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** The one sentence beside the calendar: the goal, then where this month stands. */
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
