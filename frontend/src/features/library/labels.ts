import type { EntryStatus, ItemType, SortKey } from "@/api/library";

/**
 * User-facing copy for the entry statuses. Internal names are permanent
 * (`unsorted`, `to_read`); only what the reader sees follows the brand, so the
 * mapping lives in one place instead of being re-typed per screen.
 */
export const statusLabels: Record<EntryStatus, string> = {
  unsorted: "Inbox",
  read: "Read",
  reading: "Reading",
  to_read: "To read",
  wishlist: "Wishlist",
  dropped: "Dropped",
};

/** Statuses a reader can choose directly; `unsorted` is where imports land. */
export const chooseableStatuses: readonly EntryStatus[] = [
  "read",
  "reading",
  "to_read",
  "wishlist",
  "dropped",
];

/**
 * The triage keyboard map, beside the labels it names rather than re-typed on the
 * screen that uses it: a status, what it is called and the key that sets it are one
 * table, and `labels.test.ts` asserts they cannot drift apart.
 */
export const statusHotkeys: Record<string, EntryStatus> = {
  r: "read",
  t: "to_read",
  w: "wishlist",
  d: "dropped",
  g: "reading",
  u: "unsorted",
};

/**
 * The statuses as *this* item's domain names them. The values never move — `read` is
 * a permanent internal name — but an album is listened to rather than read, so the
 * copy does (DEC-052 seam 5a). A domain that overrides nothing gets the shared table.
 */
export function statusLabelsFor(
  itemType: string,
  types: ItemType[] | undefined,
): Record<EntryStatus, string> {
  // Defensive on purpose: the registry must never be the reason a row fails to
  // render, so anything unexpected falls back to the shared vocabulary.
  const overrides = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.status_labels
    : undefined;
  return overrides ? { ...statusLabels, ...overrides } : statusLabels;
}

export const sortLabels: Record<SortKey, string> = {
  date_added: "Recently added",
  score: "Score",
  title: "Title",
  creator: "Creator",
  year: "Year",
  date_finished: "Finished",
};
