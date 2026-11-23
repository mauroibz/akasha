/** `YYYY-MM-DD` of a local date. */
export function iso(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, "0");
  const date = String(day.getDate()).padStart(2, "0");
  return `${day.getFullYear()}-${month}-${date}`;
}

function shifted(day: Date, by: number): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate() + by);
}

export type Span = "week" | "month";

/**
 * The days *Every day* draws (Sprint 147): this week, Monday to Sunday, or this
 * month. `lead` is how many empty places stand before the first day so that it
 * falls under its weekday in a Monday-first grid.
 */
export function daysOf(
  span: Span,
  today: Date,
): { days: Date[]; lead: number } {
  // Monday is 0.
  const weekday = (day: Date) => (day.getDay() + 6) % 7;
  if (span === "week") {
    const monday = shifted(today, -weekday(today));
    return {
      days: Array.from({ length: 7 }, (_, index) => shifted(monday, index)),
      lead: 0,
    };
  }
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const length = new Date(
    today.getFullYear(),
    today.getMonth() + 1,
    0,
  ).getDate();
  return {
    days: Array.from({ length }, (_, index) => shifted(first, index)),
    lead: weekday(first),
  };
}

export function longDay(day: Date): string {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(day);
}
