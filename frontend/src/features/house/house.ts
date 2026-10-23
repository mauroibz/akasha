/**
 * Dates for where things are and who has them (Sprint 111, DEC-176).
 *
 * A stored day is the owner's calendar day (`YYYY-MM-DD`), typed in the browser like
 * every other date here, so it is parsed as a local date: `new Date("2026-04-02")`
 * is UTC midnight, which is the evening of 1 April in Buenos Aires.
 */

const DAY = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
});

function localDate(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, (month || 1) - 1, date || 1);
}

/** "2 Apr 2026", in the reader's own order. */
export function readableDay(day: string): string {
  return DAY.format(localDate(day));
}

/** How long something has been out, in the unit that reads naturally. */
export function howLong(since: string, today: Date): string {
  const start = localDate(since);
  const now = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.max(
    0,
    Math.round((now.getTime() - start.getTime()) / 86_400_000),
  );
  const plural = (count: number, unit: string) =>
    `${count} ${unit}${count === 1 ? "" : "s"}`;
  if (days === 0) return "since today";
  if (days < 14) return plural(days, "day");
  if (days < 70) return plural(Math.floor(days / 7), "week");
  const months =
    (now.getFullYear() - start.getFullYear()) * 12 +
    now.getMonth() -
    start.getMonth() -
    (now.getDate() < start.getDate() ? 1 : 0);
  if (months < 24) return plural(Math.max(2, months), "month");
  return plural(Math.floor(months / 12), "year");
}
