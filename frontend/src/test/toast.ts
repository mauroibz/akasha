import { waitFor } from "@testing-library/react";

/**
 * Resolves the Sonner toast carrying `text`.
 *
 * It queries `[data-sonner-toast]` rather than by accessible text on purpose.
 * Until Sprint 015 every confirmation in this app was written into a
 * `<p className="sr-only">`, and a query by role or text passes just as happily
 * against a visually hidden element — that is exactly how thirteen sprints
 * closed on an invisible feedback layer (DEC-024). Asserting the node lives
 * inside the toast surface is what makes the test mean "the user saw it".
 *
 * jsdom applies no Tailwind CSS, so `toBeVisible()` here cannot distinguish
 * `sr-only`; the geometric proof is the Playwright assertion in
 * `e2e/feedback.spec.ts`.
 */
export async function findToast(text: string | RegExp): Promise<HTMLElement> {
  const matches = (value: string) =>
    typeof text === "string" ? value.includes(text) : text.test(value);
  let found: HTMLElement | null = null;
  await waitFor(() => {
    const toasts = Array.from(
      document.querySelectorAll<HTMLElement>("[data-sonner-toast]"),
    );
    found = toasts.find((node) => matches(node.textContent ?? "")) ?? null;
    if (!found) throw new Error(`no toast matching ${String(text)}`);
  });
  return found!;
}
