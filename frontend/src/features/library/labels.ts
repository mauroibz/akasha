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

export const sortLabels: Record<SortKey, string> = {
  date_added: "Recently added",
  score: "Score",
  title: "Title",
  sort_author: "Author",
  year: "Year",
  date_finished: "Finished",
};
