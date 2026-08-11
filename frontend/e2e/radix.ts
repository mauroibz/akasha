import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Radix does not render a native `<select>`: the trigger is a
 * `button[role="combobox"]` and the listbox is portalled to `document.body`.
 * `selectOption()` and `toHaveValue()` therefore cannot address it, and every
 * call site in this suite goes through these two helpers instead.
 */
export async function chooseOption(
  page: Page,
  trigger: Locator,
  option: string | RegExp,
) {
  await trigger.click();
  // Exact for strings: "Read" would otherwise also match "Reading" and
  // "To read", which is a strict-mode violation rather than a helpful default.
  await page
    .getByRole("option", { name: option, exact: typeof option === "string" })
    .click();
  // The listbox is dismissed before the caller asserts on the result.
  await expect(page.getByRole("listbox")).toBeHidden();
}

/** The trigger renders its current selection as text, not as a form value. */
export async function expectSelected(trigger: Locator, label: string | RegExp) {
  await expect(trigger).toContainText(label);
}
