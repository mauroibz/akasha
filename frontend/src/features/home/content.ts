import type { Home } from "@/api/home";

/** Whether a front payload has anything to draw for a key; one with nothing is left
 * out of the page until it has. */
export function hasContent(key: string, home: Home): boolean {
  if (key === "now") return home.now.length > 0;
  if (key === "lately") return Boolean(home.lately?.length);
  if (key === "next") return home.next.length > 0;
  if (key === "question") return home.question !== null;
  if (key === "suggested") return Boolean(home.suggested?.length);
  if (key.startsWith("year:"))
    return (home.library_years ?? []).some(
      (row) => `year:${row.item_type}` === key,
    );
  if (key.startsWith("shelf:"))
    return (home.shelf_modules ?? []).some((row) => `shelf:${row.id}` === key);
  // A number asks for itself and says so when it has nothing to count.
  return key.startsWith("insight:");
}
