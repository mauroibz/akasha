import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import { patchEntry, type EntryPatch, type LibraryEntry } from "@/api/library";

/**
 * A change made from Home: the same `PATCH /entries/{id}` the library and the detail
 * page send, then everything that shows the entry is read again.
 */
export function useHomeWrite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      entry,
      changes,
    }: {
      entry: LibraryEntry;
      changes: EntryPatch;
    }) => patchEntry(entry.id, changes),
    onSuccess: (_saved, { entry }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.home });
      void queryClient.invalidateQueries({ queryKey: queryKeys.now });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.entry(entry.id),
      });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Your change could not be saved",
      );
    },
  });
}
