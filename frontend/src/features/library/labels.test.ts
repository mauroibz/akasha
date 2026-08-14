import { describe, expect, it } from "vitest";

import { entryStatuses } from "@/api/library";
import {
  chooseableStatuses,
  statusHotkeys,
  statusLabels,
} from "@/features/library/labels";

/**
 * The status vocabulary lived in two places — `labels.ts` and a verbatim copy in
 * `TriagePage.tsx` — which is how one screen keeps a label the rest of the app has
 * moved on from. These assertions are what stops the copy coming back: a status,
 * its label and its hotkey are one table, and a gap in any of them fails here
 * rather than on the screen.
 */
describe("the status vocabulary", () => {
  it("labels every status the API can return", () => {
    for (const status of entryStatuses) {
      expect(statusLabels[status]).toBeTruthy();
    }
    expect(Object.keys(statusLabels).sort()).toEqual([...entryStatuses].sort());
  });

  it("gives every directly choosable status a triage hotkey", () => {
    const targets = Object.values(statusHotkeys);
    for (const status of chooseableStatuses) {
      expect(targets).toContain(status);
    }
  });

  it("binds no hotkey to a status that does not exist", () => {
    for (const [key, status] of Object.entries(statusHotkeys)) {
      expect(entryStatuses).toContain(status);
      expect(key).toBe(key.toLowerCase());
      expect(key).toHaveLength(1);
    }
  });

  it("binds each hotkey to one status", () => {
    const targets = Object.values(statusHotkeys);
    expect(new Set(targets).size).toBe(targets.length);
  });
});
