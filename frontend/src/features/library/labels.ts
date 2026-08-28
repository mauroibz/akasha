import type {
  EntryFormat,
  EntryStatus,
  FormatSpec,
  ItemType,
  ProgressSpec,
  SortKey,
  StatusSpec,
} from "@/api/library";

/**
 * The shared fallback vocabulary.
 *
 * Every screen renders the statuses its row's *domain* declares, served by
 * `/api/item-types`. This table is what it falls back to when the registry has not
 * arrived or could not be fetched: the registry must never be the reason a row is
 * unreadable. It is the book vocabulary because books are what a library holds when
 * nothing else is known.
 *
 * **Partial on purpose.** A domain added later must not have to edit this table to be
 * readable — an exhaustive `Record` made a new status a TypeScript error here, which is
 * a coupling a domain should not pay for a fallback that only shows before the registry
 * arrives. Anything absent falls back to the stored value, which is legible.
 */
export const statusLabels: Partial<Record<EntryStatus, string>> = {
  unsorted: "Inbox",
  read: "Read",
  reading: "Reading",
  to_read: "To read",
  wishlist: "Wishlist",
  dropped: "Dropped",
  pending: "On the way",
  owned: "Owned",
};

/** The same fallback, in the order and shape the controls take. */
export const fallbackStatuses: readonly StatusSpec[] = [
  { value: "unsorted", label: "Inbox", choosable: false, hotkey: "u" },
  { value: "read", label: "Read", choosable: true, hotkey: "r" },
  { value: "reading", label: "Reading", choosable: true, hotkey: "g" },
  { value: "to_read", label: "To read", choosable: true, hotkey: "t" },
  { value: "wishlist", label: "Wishlist", choosable: true, hotkey: "w" },
  { value: "dropped", label: "Dropped", choosable: true, hotkey: "d" },
];

/**
 * The domains, or nothing at all.
 *
 * Every consumer here already tolerates a registry that has not arrived; this is the
 * same rule for a screen that iterates the whole list rather than looking one domain
 * up, so a failed or unexpected response renders a page without chips instead of no
 * page at all.
 */
export function domainsFrom(types: ItemType[] | undefined): ItemType[] {
  return Array.isArray(types) ? types : [];
}

/**
 * The statuses *this* item's domain has (seam 5b, DEC-057).
 *
 * Seam 5a made this a label lookup, because every domain held the same values under
 * different names. It is a vocabulary lookup now: an album has `owned` and no `read`
 * at all, so a component that assumed one list would offer a status the API refuses.
 */
export function statusesFor(
  itemType: string,
  types: ItemType[] | undefined,
): readonly StatusSpec[] {
  // Defensive on purpose: the registry must never be the reason a row fails to
  // render, so anything unexpected falls back to the shared vocabulary.
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.statuses
    : undefined;
  return declared?.length ? declared : fallbackStatuses;
}

/** What this domain calls one status, for a place with room for a word and not a list. */
export function statusLabelFor(
  itemType: string,
  types: ItemType[] | undefined,
  status: EntryStatus,
): string {
  const spec = statusesFor(itemType, types).find((row) => row.value === status);
  // The stored value is the last resort, and a perfectly readable one: a domain
  // registered after this table was written should render as `playing`, not as blank.
  return spec?.label ?? statusLabels[status] ?? status;
}

/**
 * The triage keyboard map for a row, derived from its domain rather than from a
 * second table beside this one. `w` is wishlist in both domains and `o` exists only
 * for albums, which is exactly the drift a hand-maintained copy would acquire.
 */
export function hotkeysFor(
  itemType: string,
  types: ItemType[] | undefined,
): Record<string, EntryStatus> {
  const map: Record<string, EntryStatus> = {};
  for (const status of statusesFor(itemType, types)) {
    if (status.hotkey) map[status.hotkey] = status.value;
  }
  return map;
}

/** The formats this domain declares. Closed, and never free text (DEC-059). */
export function formatsFor(
  itemType: string,
  types: ItemType[] | undefined,
): readonly FormatSpec[] {
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.formats
    : undefined;
  return Array.isArray(declared) ? declared : [];
}

/** What a format is called, wherever it is rendered away from its domain. */
export function formatLabels(
  types: ItemType[] | undefined,
): Record<string, string> {
  const labels: Record<string, string> = {};
  for (const type of types ?? []) {
    // Defensive for the same reason as `statusesFor`: a registry that is older,
    // partial or unreachable must never be what stops a row from rendering.
    for (const row of type.formats ?? []) labels[row.value] = row.label;
  }
  return labels;
}

/** Whether this domain's entries have a field at all (DEC-057). */
export function hasEntryField(
  itemType: string,
  types: ItemType[] | undefined,
  field: EntryFieldName,
): boolean {
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.entry_fields
    : undefined;
  // Unknown domain: assume the book shape rather than hiding a reader's own data.
  return declared ? declared.includes(field) : true;
}

/**
 * The neutral name of a passage field, used where a domain does not rename it.
 *
 * Deliberately not a book's words. `Started` and `Finished` are right for a book, a
 * series and anything else that takes time; `reread_count` has no neutral English word
 * at all, so the fallback is the flattest one available and the domains that care say
 * what they mean. Before this, the detail page said `Rereads` over every domain.
 */
const neutralEntryFieldLabels: Record<EntryFieldName, string> = {
  date_started: "Started",
  date_finished: "Finished",
  reread_count: "Repeats",
};

export type EntryFieldName = "date_started" | "date_finished" | "reread_count";

/** What *this* domain calls one of its passage fields. */
export function entryFieldLabel(
  itemType: string,
  types: ItemType[] | undefined,
  field: EntryFieldName,
): string {
  // Defensive for the same reason as `statusesFor`: a registry that has not arrived
  // must never be the reason a control loses its name.
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.entry_field_labels
    : undefined;
  return declared?.[field] ?? neutralEntryFieldLabels[field];
}

/**
 * How this domain counts progress, or `null` where that means nothing (DEC-077).
 *
 * The fallback is deliberately **not** the book shape its neighbours here use.
 * `hasEntryField` and `choosesCovers` assume a domain *has* the thing when the
 * registry has not arrived, because guessing wrong there hides a reader's own data.
 * There is no neutral progress concept to guess: without a declaration there is no
 * label and no unit, and an unlabelled number box is worse than no box at all for
 * the moment before `/api/item-types` lands.
 */
export function progressFor(
  itemType: string,
  types: ItemType[] | undefined,
): ProgressSpec | null {
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.progress
    : undefined;
  return declared ?? null;
}

/** Whether this domain offers the cover chooser at all (DEC-067 row 7). */
export function choosesCovers(
  itemType: string,
  types: ItemType[] | undefined,
): boolean {
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.chooses_covers
    : undefined;
  // Unknown domain: the book shape, as everywhere else here. A registry that has not
  // arrived must never be the reason a control the reader expects is missing.
  return declared ?? true;
}

/**
 * The domain's own name for one of its things, for copy that has to name it.
 *
 * This is what deliverable 6 of Sprint 029 replaced eighteen hardcoded "book"s
 * with: a toast that said *Book added* over an album is wrong in a way no
 * rendering-layer neutrality fixes, because the word is the message. Copy either
 * comes from here or is written to name nothing.
 *
 * The fallback is deliberately generic rather than "Book". Everywhere else in this
 * file an unknown domain assumes the book shape, because guessing wrong there hides
 * a reader's own data; here guessing wrong just puts the wrong noun on a screen, and
 * "Item" is wrong for nobody.
 */
export function labelFor(
  itemType: string,
  types: ItemType[] | undefined,
): string {
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.label
    : undefined;
  return declared ?? "Item";
}

export function entryPanelLabel(
  itemType: string,
  types: ItemType[] | undefined,
): string {
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.entry_panel_label
    : undefined;
  return declared ?? "Your reading data";
}

export type { EntryFormat };

export const sortLabels: Record<SortKey, string> = {
  date_added: "Recently added",
  score: "Score",
  title: "Title",
  creator: "Creator",
  year: "Year",
  date_finished: "Finished",
};
