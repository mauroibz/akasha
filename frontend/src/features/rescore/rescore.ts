import type { EntryStatus, ItemType, LibraryEntry } from "@/api/library";

/**
 * Finishing again asks whether the score still holds (Sprint 115, DEC-176). What
 * "finished" and "under way" mean is each domain's declaration, so nothing here names
 * "read" or "watched".
 */

type Flag = "finished" | "in_progress" | "planned";

/** The status a domain declares with `flag`, or `null` when it has none. */
export function statusWith(
  itemType: string,
  types: ItemType[] | undefined,
  flag: Flag,
): EntryStatus | null {
  const statuses = Array.isArray(types)
    ? types.find((type) => type.id === itemType)?.statuses
    : undefined;
  return statuses?.find((status) => status[flag])?.value ?? null;
}

export function isFinished(
  entry: Pick<LibraryEntry, "status" | "item">,
  types: ItemType[] | undefined,
): boolean {
  return statusWith(entry.item.type, types, "finished") === entry.status;
}

/**
 * Whether a save that took `before` to `after` should ask "Still an 8?": the entry
 * moved into its finished status, already had a score, and this save did not set
 * one (a score chosen in the same breath is its own answer).
 */
export function askStill(
  before: Pick<LibraryEntry, "status" | "score">,
  after: LibraryEntry,
  types: ItemType[] | undefined,
): boolean {
  return (
    before.status !== after.status &&
    isFinished(after, types) &&
    after.score !== null &&
    before.score === after.score
  );
}

/** Why the answer is what it is: a pass begun with *Start again* is a reread. */
export function stillReason(entry: Pick<LibraryEntry, "reread_count">) {
  return entry.reread_count > 0 ? ("reread" as const) : ("time" as const);
}

/** "an 8", "a 9": the article a score takes read aloud. */
export function scoreArticle(score: number): string {
  return `${score === 8 || score === 11 || score === 18 ? "an" : "a"} ${score}`;
}
