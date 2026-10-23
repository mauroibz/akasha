import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { queryKeys } from "@/api/keys";
import { patchEntry, type LibraryEntry } from "@/api/library";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { localDay } from "@/features/progress/outline";
import { scoreChipClass } from "@/lib/score";
import { cn } from "@/lib/utils";

import { scoreArticle, stillReason } from "./rescore";

/**
 * "Still an 8?" (Sprint 115, DEC-176): asked when a scored entry is finished again.
 * Keeping the score is a row of history too; changing it records the new one with why
 * (a reread, or time) and a line of the owner's own. *Not now* writes nothing.
 *
 * `again` is the film's case, a domain with nothing under way: watching it again is
 * the whole pass, so the answer also records the day and the count.
 */
export function StillDialog(props: {
  entry: LibraryEntry | null;
  again?: boolean;
  onClose: () => void;
  onSaved?: (saved: LibraryEntry) => void;
}) {
  if (!props.entry || props.entry.score === null) return null;
  return <Asked key={props.entry.id} {...props} entry={props.entry} />;
}

function Asked({
  entry,
  again = false,
  onClose,
  onSaved,
}: {
  entry: LibraryEntry;
  again?: boolean;
  onClose: () => void;
  onSaved?: (saved: LibraryEntry) => void;
}) {
  const queryClient = useQueryClient();
  const was = entry.score!;
  const [score, setScore] = useState(was);
  const [why, setWhy] = useState("");
  const save = useMutation({
    mutationFn: () =>
      patchEntry(entry.id, {
        score,
        score_reason: again ? "reread" : stillReason(entry),
        ...(why.trim() ? { score_note: why.trim() } : {}),
        ...(again
          ? {
              date_finished: localDay(new Date()),
              reread_count: entry.reread_count + 1,
            }
          : {}),
      }),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.entry(entry.id), saved);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.entry(entry.id),
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.scoreHistory(entry.id),
      });
      onSaved?.(saved);
      onClose();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const changed = score !== was;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="contents">
          <DialogHeader>
            <DialogTitle>Still {scoreArticle(was)}?</DialogTitle>
            <DialogDescription>
              {again
                ? `Another time through ${entry.item.title}.`
                : `You finished ${entry.item.title} again.`}{" "}
              Keep the score, or give the one it has now.
            </DialogDescription>
          </DialogHeader>
          <fieldset>
            <legend className="sr-only">Score</legend>
            <div className="flex gap-1">
              {Array.from({ length: 10 }, (_, index) => index + 1).map(
                (value) => (
                  <button
                    key={value}
                    type="button"
                    aria-label={`Score ${value}`}
                    aria-pressed={score === value}
                    onClick={() => setScore(value)}
                    className={cn(
                      "h-10 min-w-0 flex-1 rounded-md text-sm font-medium tabular-nums transition-colors focus-ring",
                      score === value
                        ? scoreChipClass(value)
                        : "bg-surface text-muted-foreground hover:bg-accent hover:text-foreground",
                      value === was &&
                        score !== was &&
                        "outline-dashed outline-1 outline-offset-2 outline-muted-foreground",
                    )}
                  >
                    {value}
                  </button>
                ),
              )}
            </div>
          </fieldset>
          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">
              Why, in a line (optional)
            </span>
            <Input
              value={why}
              maxLength={280}
              onChange={(event) => setWhy(event.target.value)}
              placeholder={changed ? "What changed" : "What still holds"}
            />
          </label>
          {save.error && (
            <p role="alert" className="text-sm text-destructive">
              {save.error.message}
            </p>
          )}
          <DialogFooter className="gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Not now
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {changed ? `Change to ${score}` : `Keep ${was}`}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
