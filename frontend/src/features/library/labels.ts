import type { EntryStatus, SortKey } from "@/api/library";

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

export const sortLabels: Record<SortKey, string> = {
  date_added: "Recently added",
  score: "Score",
  title: "Title",
  sort_author: "Author",
  year: "Year",
  date_finished: "Finished",
};
