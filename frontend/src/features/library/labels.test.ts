import { describe, expect, it } from "vitest";

import { entryFormats, entryStatuses, type ItemType } from "@/api/library";
import {
  fallbackStatuses,
  formatsFor,
  hasEntryField,
  hotkeysFor,
  statusLabels,
  statusesFor,
} from "@/features/library/labels";

/**
 * The status vocabulary lived in two places — `labels.ts` and a verbatim copy in
 * `TriagePage.tsx` — which is how one screen keeps a label the rest of the app has
 * moved on from. These assertions are what stops the copy coming back.
 *
 * They now run **per domain**, over a registry payload, because a status, its label
 * and its hotkey are one table *for each domain* (seam 5b). A rule checked against
 * one vocabulary is a rule the second one quietly breaks.
 */
const registry: ItemType[] = [
  {
    id: "book",
    label: "Book",
    fields: [],
    statuses: [...fallbackStatuses],
    default_status: "read",
    entry_fields: ["date_started", "date_finished", "reread_count"],
    formats: [
      { value: "physical", label: "Physical" },
      { value: "borrowed", label: "Borrowed" },
      { value: "digital", label: "Digital" },
    ],
    entry_panel_label: "Your reading data",
    chooses_covers: true,
  },
  {
    id: "album",
    label: "Album",
    fields: [],
    statuses: [
      { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
      { value: "wishlist", label: "Wishlist", choosable: true, hotkey: "w" },
      { value: "pending", label: "On the way", choosable: true, hotkey: "p" },
      { value: "owned", label: "Owned", choosable: true, hotkey: "o" },
    ],
    default_status: "owned",
    entry_fields: [],
    formats: [
      { value: "vinyl", label: "Vinyl" },
      { value: "cd", label: "CD" },
      { value: "digital", label: "Digital" },
    ],
    entry_panel_label: "Your copy",
    chooses_covers: false,
  },
];

describe("the status vocabulary", () => {
  it("labels every status the API can return", () => {
    for (const status of entryStatuses) {
      expect(statusLabels[status]).toBeTruthy();
    }
    expect(Object.keys(statusLabels).sort()).toEqual([...entryStatuses].sort());
  });

  it.each(registry)("gives $id a complete, non-drifting table", (type) => {
    const statuses = statusesFor(type.id, registry);
    const hotkeys = hotkeysFor(type.id, registry);
    for (const status of statuses) {
      expect(status.label).toBeTruthy();
      expect(entryStatuses).toContain(status.value);
      // Every status a reader can choose is reachable from the keyboard.
      if (status.choosable)
        expect(Object.values(hotkeys)).toContain(status.value);
    }
    for (const [key, status] of Object.entries(hotkeys)) {
      expect(key).toBe(key.toLowerCase());
      expect(key).toHaveLength(1);
      expect(statuses.map((row) => row.value)).toContain(status);
    }
    // One key, one status — within a domain. `w` meaning wishlist in both is fine;
    // `w` meaning two different things on one screen is not.
    expect(new Set(Object.values(hotkeys)).size).toBe(
      Object.values(hotkeys).length,
    );
    // The inbox exists everywhere and is never something to choose.
    expect(statuses.find((row) => row.value === "unsorted")?.choosable).toBe(
      false,
    );
  });

  it.each(registry)("gives $id a closed format vocabulary", (type) => {
    const formats = formatsFor(type.id, registry);
    expect(formats.length).toBeGreaterThan(0);
    for (const format of formats) {
      expect(entryFormats).toContain(format.value);
      expect(format.label).toBeTruthy();
    }
  });

  it("falls back to the shared vocabulary rather than rendering nothing", () => {
    expect(statusesFor("book", undefined)).toEqual(fallbackStatuses);
    expect(statusesFor("wine", registry)).toEqual(fallbackStatuses);
    // An unknown domain keeps the reader's own fields rather than hiding them.
    expect(hasEntryField("wine", registry, "reread_count")).toBe(true);
  });

  it("knows which domains have no passage fields at all (DEC-057)", () => {
    expect(hasEntryField("book", registry, "reread_count")).toBe(true);
    expect(hasEntryField("album", registry, "reread_count")).toBe(false);
    expect(hasEntryField("album", registry, "date_finished")).toBe(false);
  });
});
