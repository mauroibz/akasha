import type { HomeCover, HomeYear, HomeYearGoal } from "@/api/home";

/** `YYYY-MM-DD` as a local day: `new Date("2026-11-22")` would be UTC midnight. */
export function localDate(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, (month || 1) - 1, date || 1);
}

/** The most cells a month draws; the rest is a count. */
export const MONTH_CELLS = 4;

export interface MonthCell {
  month: number;
  /** The lead goal's domain's finishes (every finish when no goal is set). */
  covers: HomeCover[];
  /** Finishes in other libraries that month, drawn as a count. */
  others: number;
  /** Room the goal still has here: only from this month on, never "behind". */
  empty: number;
  current: boolean;
}

/** The goal the Year module leads with: the first one, in registry order. */
export function leadGoal(year: HomeYear): HomeYearGoal | null {
  return year.goals[0] ?? null;
}

/**
 * The year as twelve cells (Sprint 130). Months gone by show what was finished and
 * nothing else: DEC-169's goals never say behind, so a short month is not marked.
 * From this month on, each month has room for the goal's pace, and all that room
 * together is no more than what the goal still needs.
 */
export function yearCells(year: HomeYear, today: Date): MonthCell[] {
  const goal = leadGoal(year);
  const isThisYear = year.year === today.getFullYear();
  const currentMonth = isThisYear
    ? today.getMonth() + 1
    : year.year < today.getFullYear()
      ? 13
      : 0;
  const pace = goal
    ? goal.period === "month"
      ? goal.count
      : Math.ceil(goal.count / 12)
    : 0;
  let remaining = goal ? Math.max(0, goal.target - goal.done) : 0;
  return year.months.map((month) => {
    const covers = goal
      ? month.covers.filter((cover) => cover.item_type === goal.item_type)
      : month.covers;
    const leadCount = goal ? (month.counts[goal.item_type] ?? 0) : month.count;
    let empty = 0;
    if (goal && month.month >= currentMonth) {
      empty = Math.min(Math.max(0, pace - leadCount), remaining);
      remaining -= empty;
    }
    return {
      month: month.month,
      covers,
      others: month.count - leadCount,
      empty,
      current: isThisYear && month.month === currentMonth,
    };
  });
}
