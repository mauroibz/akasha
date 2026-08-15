import type {
  EntryFormat,
  EntryStatus,
  FormatSpec,
  ItemType,
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
 */
export const statusLabels: Record<EntryStatus, string> = {
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
  return spec?.label ?? statusLabels[status];
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
  field: "date_started" | "date_finished" | "reread_count",
): boolean {
  const declared = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.entry_fields
    : undefined;
  // Unknown domain: assume the book shape rather than hiding a reader's own data.
  return declared ? declared.includes(field) : true;
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
