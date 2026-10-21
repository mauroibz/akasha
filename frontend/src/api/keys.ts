/**
 * Every React Query key in the application, in one place (Sprint 088).
 *
 * A key written inline in two files is two keys that must be kept equal by hand:
 * an invalidation that names `["library"]` only reaches the queries whose key
 * starts with exactly that. Building them here makes the prefix relationships
 * (every `library.list(...)` sits under `library.all`) a property of the code.
 */
export const queryKeys = {
  library: {
    all: ["library"] as const,
    list: <F>(filters: F) => ["library", filters] as const,
  },
  libraryWhole: (domain: string) => ["library-whole", domain] as const,
  triage: {
    all: ["triage"] as const,
    list: <F>(filters: F) => ["triage", filters] as const,
  },
  entry: (entryId: number) => ["entry", entryId] as const,
  coverCandidates: (itemId: number) => ["cover-candidates", itemId] as const,
  itemTypes: ["item-types"] as const,
  insightMembers: (type: string, insightKey: string, value: string) =>
    ["insight-members", type, insightKey, value] as const,
  providerHealth: ["provider-health"] as const,
  shelves: ["shelves"] as const,
  shelfEntries: {
    /** Every page of one shelf, whichever domain it is filtered to. */
    shelf: (slug: string | undefined) => ["shelf-entries", slug] as const,
    list: (slug: string | undefined, domain: string | null | undefined) =>
      ["shelf-entries", slug, domain] as const,
  },
  users: ["users"] as const,
};
