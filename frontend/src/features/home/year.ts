/** `YYYY-MM-DD` as a local day: `new Date("2026-11-22")` would be UTC midnight. */
export function localDate(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, (month || 1) - 1, date || 1);
}
