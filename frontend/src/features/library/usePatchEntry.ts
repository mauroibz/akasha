import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { patchEntry } from "@/api/library";
import type { LibraryEntry, LibraryPage } from "@/api/library";

export type EntryChanges = Partial<Pick<LibraryEntry, "score" | "status">>;

type Pages = { pages: LibraryPage[]; pageParams: unknown[] };

/**
 * A score or status change shown at once, and put back if the server refuses it.
 *
 * Library and Triage each carried a copy of this until Sprint 088. The page passes
 * the key of the list on screen; the key is captured when the change starts, so a
 * failure restores the list that was showing then, not whatever sort is on screen
 * when the error arrives.
 */
export function usePatchEntry({
  key,
  onRollback,
  onSaved,
}: {
  key: readonly unknown[];
  /** The row whose value reverted, so the page can mark it (DEC-028). */
  onRollback?: (entry: LibraryEntry) => void;
  onSaved?: (saved: LibraryEntry, changes: EntryChanges) => void;
}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      entry,
      changes,
    }: {
      entry: LibraryEntry;
      changes: EntryChanges;
    }) => patchEntry(entry.id, changes),
    onMutate: async ({ entry, changes }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const snapshot = queryClient.getQueryData(key);
      queryClient.setQueryData<Pages>(
        key,
        (old) =>
          old && {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((row) =>
                row.id === entry.id
                  ? {
                      ...row,
                      ...changes,
                      score_provisional:
                        changes.score === undefined
                          ? row.score_provisional
                          : false,
                    }
                  : row,
              ),
            })),
          },
      );
      return { key, snapshot };
    },
    onError: (_error, { entry }, context) => {
      if (context) queryClient.setQueryData(context.key, context.snapshot);
      onRollback?.(entry);
      toast.error("Your change could not be saved", {
        description: "The previous value was restored.",
      });
    },
    onSuccess: (saved, { changes }) => onSaved?.(saved, changes),
  });
}
