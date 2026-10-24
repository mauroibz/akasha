import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { queryKeys } from "@/api/keys";
import {
  patchEntry,
  type EntryFormat,
  type EntryPatch,
  type ItemType,
  type LibraryEntry,
} from "@/api/library";
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
import { hasEntryField } from "@/features/library/labels";
import { localDay } from "@/features/progress/outline";
import {
  scoreArticle,
  statusWith,
  stillReason,
} from "@/features/rescore/rescore";
import { scoreChipClass } from "@/lib/score";
import { cn } from "@/lib/utils";

type When = "today" | "yesterday" | "other";

function yesterday(): string {
  const day = new Date();
  day.setDate(day.getDate() - 1);
  return localDay(day);
}

/**
 * Finishing, in one sheet (Sprint 123, DEC-179, mockup 1C): what is known at the
 * moment something ends is asked then. When (today chosen), the score, and the
 * format if none is recorded. Every question has an answer already, so *Finish* at
 * once is the skip. A score already given is asked as "Still an 8?", and keeping it
 * is a row of the score history, as the *Still* dialog records it.
 */
export function FinishDialog(props: {
  entry: LibraryEntry | null;
  types: ItemType[] | undefined;
  onClose: () => void;
  onFinished?: (saved: LibraryEntry) => void;
}) {
  if (!props.entry) return null;
  return <Sheet key={props.entry.id} {...props} entry={props.entry} />;
}

function Sheet({
  entry,
  types,
  onClose,
  onFinished,
}: {
  entry: LibraryEntry;
  types: ItemType[] | undefined;
  onClose: () => void;
  onFinished?: (saved: LibraryEntry) => void;
}) {
  const queryClient = useQueryClient();
  const type = entry.item.type;
  const finished = statusWith(type, types, "finished");
  const dated = hasEntryField(type, types, "date_finished");
  const formats =
    (entry.formats ?? []).length === 0
      ? ((Array.isArray(types) ? types : []).find((row) => row.id === type)
          ?.formats ?? [])
      : [];
  const was = entry.score;
  const [when, setWhen] = useState<When>("today");
  const [other, setOther] = useState(yesterday());
  const [score, setScore] = useState<number | null>(was);
  const [why, setWhy] = useState("");
  const [chosen, setChosen] = useState<EntryFormat[]>([]);

  const save = useMutation({
    mutationFn: () => {
      const changes: EntryPatch = { status: finished! };
      if (dated)
        changes.date_finished =
          when === "today"
            ? localDay(new Date())
            : when === "yesterday"
              ? yesterday()
              : other;
      if (was !== null) {
        // Kept or changed, the answer is history (Sprint 115).
        changes.score = score ?? was;
        changes.score_reason = stillReason(entry);
        if (why.trim()) changes.score_note = why.trim();
      } else if (score !== null) changes.score = score;
      if (chosen.length) changes.formats = chosen;
      return patchEntry(entry.id, changes);
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.entry(entry.id), saved);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.entry(entry.id),
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.now });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.scoreHistory(entry.id),
      });
      onFinished?.(saved);
      onClose();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  if (!finished) return null;

  const choice = (value: When, label: string) => (
    <button
      type="button"
      aria-pressed={when === value}
      onClick={() => setWhen(value)}
      className={cn(
        "min-h-11 rounded-full border px-4 text-sm font-medium transition-colors focus-ring",
        when === value
          ? "border-transparent bg-primary text-primary-foreground"
          : "border-border bg-surface hover:bg-accent",
      )}
    >
      {label}
    </button>
  );

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="contents">
          <DialogHeader>
            <DialogTitle>You finished {entry.item.title}</DialogTitle>
            <DialogDescription>
              Anything you leave as it is stays as it was.
            </DialogDescription>
          </DialogHeader>
          {dated && (
            <fieldset className="space-y-2">
              <legend className="mb-2 text-sm text-muted-foreground">
                When
              </legend>
              <div className="flex flex-wrap gap-2">
                {choice("today", "Today")}
                {choice("yesterday", "Yesterday")}
                {choice("other", "Another day")}
              </div>
              {when === "other" && (
                <Input
                  type="date"
                  aria-label="The day you finished"
                  value={other}
                  max={localDay(new Date())}
                  onChange={(event) => setOther(event.target.value)}
                  className="w-auto"
                />
              )}
            </fieldset>
          )}
          <fieldset>
            <legend className="mb-2 text-sm text-muted-foreground">
              {was !== null ? `Still ${scoreArticle(was)}?` : "Score"}
            </legend>
            <div className="flex gap-1">
              {Array.from({ length: 10 }, (_, index) => index + 1).map(
                (value) => (
                  <button
                    key={value}
                    type="button"
                    aria-label={`Score ${value}`}
                    aria-pressed={score === value}
                    onClick={() =>
                      // A new score can be taken back; an old one is kept by
                      // choosing it again.
                      setScore(score === value && was === null ? null : value)
                    }
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
          {was !== null && (
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                Why, in a line (optional)
              </span>
              <Input
                value={why}
                maxLength={280}
                onChange={(event) => setWhy(event.target.value)}
                placeholder={
                  score !== was ? "What changed" : "What still holds"
                }
              />
            </label>
          )}
          {formats.length > 0 && (
            <fieldset>
              <legend className="mb-2 text-sm text-muted-foreground">
                How you had it
              </legend>
              <div className="flex flex-wrap gap-2">
                {formats.map((format) => {
                  const on = chosen.includes(format.value as EntryFormat);
                  return (
                    <button
                      key={format.value}
                      type="button"
                      aria-pressed={on}
                      onClick={() =>
                        setChosen((rows) =>
                          on
                            ? rows.filter((row) => row !== format.value)
                            : [...rows, format.value as EntryFormat],
                        )
                      }
                      className={cn(
                        "min-h-11 rounded-full border px-4 text-sm transition-colors focus-ring",
                        on
                          ? "border-primary bg-primary/15 font-medium text-primary"
                          : "border-border bg-surface hover:bg-accent",
                      )}
                    >
                      {format.label}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          )}
          {save.error && (
            <p role="alert" className="text-sm text-destructive">
              {save.error.message}
            </p>
          )}
          <DialogFooter className="gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              Finish
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
