import { describe, expect, it } from "vitest";

import { entryFormats, entryStatuses, type ItemType } from "@/api/library";
import {
  entryFieldLabel,
  progressFor,
  fallbackStatuses,
  formatsFor,
  hasEntryField,
  hotkeysFor,
  statusLabelFor,
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
    entry_field_labels: { reread_count: "Rereads" },
    progress: null,
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
    entry_field_labels: {},
    progress: null,
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
  it("never renders nothing for a status the API can return", () => {
    // The fallback table is deliberately partial, so a domain added later needs no edit
    // here (DEC-067 row 10). What must hold is that the *lookup* always answers: with
    // the domain's own label, else the shared fallback, else the stored value.
    for (const status of entryStatuses) {
      expect(statusLabelFor("book", undefined, status)).toBeTruthy();
    }
    // Every fallback it does carry belongs to the published union — a label for a value
    // no domain can hold is dead copy.
    for (const value of Object.keys(statusLabels)) {
      expect([...entryStatuses]).toContain(value);
    }
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

describe("entryFieldLabel", () => {
  it("uses the domain's own word for a passage field", () => {
    // The entry panel said `Rereads` over every domain until the label became the
    // domain's copy, the way `entry_panel_label` already was.
    expect(entryFieldLabel("book", registry, "reread_count")).toBe("Rereads");
  });

  it("falls back to a neutral word, not to a book's", () => {
    // An album declares no labels at all, and a domain this registry has never heard
    // of must still render a named control rather than a blank one.
    expect(entryFieldLabel("album", registry, "reread_count")).toBe("Repeats");
    expect(entryFieldLabel("nonesuch", registry, "reread_count")).toBe(
      "Repeats",
    );
  });

  it("leaves the dates alone, because the neutral word is already right", () => {
    expect(entryFieldLabel("book", registry, "date_started")).toBe("Started");
    expect(entryFieldLabel("book", registry, "date_finished")).toBe("Finished");
  });

  it("still names the field when the registry never arrived", () => {
    expect(entryFieldLabel("book", undefined, "date_started")).toBe("Started");
  });
});

describe("progressFor", () => {
  const withProgress: ItemType[] = [
    {
      ...registry[0],
      id: "anime",
      label: "Anime",
      progress: {
        label: "Episodes watched",
        unit_label: "episode",
        total_field: "episodes",
      },
    },
  ];

  it("returns the domain's own declaration", () => {
    expect(progressFor("anime", withProgress)).toEqual({
      label: "Episodes watched",
      unit_label: "episode",
      total_field: "episodes",
    });
  });

  it("returns null for a domain that counts nothing", () => {
    expect(progressFor("book", registry)).toBeNull();
    expect(progressFor("album", registry)).toBeNull();
  });

  it("returns null rather than guessing when the registry never arrived", () => {
    // Deliberately unlike `hasEntryField` and `choosesCovers`, which fall back to the
    // book shape so a missing registry never hides a reader's own data. There is no
    // neutral progress concept to fall back *to*: an unlabelled number box is worse
    // than no box for the moment before `/api/item-types` lands.
    expect(progressFor("anime", undefined)).toBeNull();
    expect(progressFor("nonesuch", registry)).toBeNull();
  });
});
