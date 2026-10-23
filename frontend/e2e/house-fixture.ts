import type { Page } from "@playwright/test";

import { bookType, series } from "./progress-fixture";

/**
 * A book with a place and a loan history, stubbed statefully as Sprint 110's API
 * answers (Sprint 111): shared by the lent spec and the accessibility suite.
 */

export function today() {
  const now = new Date();
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}

export async function stubHouse(page: Page) {
  let current: Record<string, unknown> = series({
    item: {
      ...series().item,
      type: "book",
      title: "Rayuela",
      outline: [],
      metadata: { creators: ["Julio Cortázar"] },
    },
  });
  let loans: Array<Record<string, unknown>> = [];
  await page.route("**/api/item-types", (route) =>
    route.fulfill({ json: [bookType] }),
  );
  await page.route("**/api/shelves", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/items/3/attachments", (route) =>
    route.fulfill({ json: { attachments: [] } }),
  );
  await page.route("**/api/locations", (route) =>
    route.fulfill({ json: [{ location: "Hall", count: 4 }] }),
  );
  const open = () => loans.find((loan) => loan.returned_on === null) ?? null;
  await page.route("**/api/entries/7", async (route) => {
    if (route.request().method() === "PATCH")
      current = { ...current, ...route.request().postDataJSON() };
    await route.fulfill({ json: { ...current, loan: open() } });
  });
  await page.route("**/api/entries/7/loans", async (route) => {
    if (route.request().method() === "POST") {
      const loan = {
        id: loans.length + 1,
        entry_id: 7,
        returned_on: null,
        note: null,
        ...route.request().postDataJSON(),
      };
      loans = [...loans, loan];
      return route.fulfill({ status: 201, json: loan });
    }
    await route.fulfill({ json: [...loans].reverse() });
  });
  await page.route("**/api/loans/*", async (route) => {
    const id = Number(route.request().url().split("/").pop());
    const body = route.request().postDataJSON() as Record<string, unknown>;
    loans = loans.map((loan) => (loan.id === id ? { ...loan, ...body } : loan));
    await route.fulfill({ json: loans.find((loan) => loan.id === id) });
  });
  await page.route("**/api/loans?open=true", (route) =>
    route.fulfill({
      json: loans
        .filter((loan) => loan.returned_on === null)
        .map((loan) => ({ ...loan, entry: { ...current, loan: open() } })),
    }),
  );
}
