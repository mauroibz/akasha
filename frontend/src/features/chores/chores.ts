import { defaultLibraryFilters } from "@/features/library/library";
import type { EntryStatus, ItemType, LibraryFilters } from "@/api/library";

/**
 * The queues the deck's chores go through (Sprint 112, DEC-176), each a library
 * filter, so a chore's count is the list endpoint's own total.
 */

/** Every status a domain declares as waiting to be started: the planned pile. */
export function plannedStatuses(types: ItemType[] | undefined): EntryStatus[] {
  const statuses = new Set<EntryStatus>();
  for (const type of Array.isArray(types) ? types : [])
    for (const status of type.statuses)
      if (status.planned) statuses.add(status.value);
  return Array.from(statuses);
}

/** The planned pile, oldest added first: what has waited longest comes up first. */
export function plannedFilters(types: ItemType[] | undefined): LibraryFilters {
  return {
    ...defaultLibraryFilters,
    statuses: plannedStatuses(types),
    sort: "date_added",
    order: "asc",
  };
}

/** Everything without a cover, oldest added first; the inbox is left to the inbox. */
export const coverlessFilters: LibraryFilters = {
  ...defaultLibraryFilters,
  sort: "date_added",
  order: "asc",
  cover: "missing",
};
