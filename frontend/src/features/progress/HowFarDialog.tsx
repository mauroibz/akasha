import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import {
  patchEntry,
  type ItemType,
  type LibraryEntry,
  type ProgressMarks,
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
import { Lights } from "@/features/progress/Lights";
import {
  capital,
  countMarks,
  drawnMarks,
  fillThrough,
} from "@/features/progress/marks";
import {
  outlineContext,
  type OutlineContext,
} from "@/features/progress/outline";

/**
 * Asked when an entry is set to a status its domain declares abandoned (DEC-172,
 * the owner: "if i add 'dropped' as a status ask me how far i got into it").
 *
 * One tap on the last episode or chapter finished lights everything up to it; with
 * no outline, a count. *Skip* closes it and writes nothing: the question is an
 * offer, never a step the drop depends on.
 */
export function HowFarDialog(props: {
  /** The entry just dropped, or `null` when nothing is being asked. */
  entry: LibraryEntry | null;
  types: ItemType[] | undefined;
  onClose: () => void;
  onSaved?: (saved: LibraryEntry) => void;
}) {
  const context = props.entry ? outlineContext(props.entry, props.types) : null;
  if (!props.entry || !context) return null;
  // Keyed, so a second drop starts from that entry's own marks.
  return (
    <Asked
      key={props.entry.id}
      {...props}
      entry={props.entry}
      context={context}
    />
  );
}

function Asked({
  entry,
  context,
  onClose,
  onSaved,
}: {
  entry: LibraryEntry;
  context: OutlineContext;
  onClose: () => void;
  onSaved?: (saved: LibraryEntry) => void;
}) {
  const inputId = useId();
  const queryClient = useQueryClient();
  const [marks, setMarks] = useState<ProgressMarks>(() =>
    drawnMarks(entry.progress_marks, entry.progress, context.outline),
  );
  const [count, setCount] = useState(
    entry.progress == null ? "" : String(entry.progress),
  );

  const save = useMutation({
    mutationFn: (
      changes: { progress_marks: ProgressMarks } | { progress: number },
    ) => patchEntry(entry.id, changes),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.entry(saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      onSaved?.(saved);
      onClose();
    },
    onError: () => toast.error("How far you got could not be saved"),
  });

  const { progress, outline, partLabel } = context;
  const unit = progress.unit_label;
  const total = outline.reduce((sum, part) => sum + part.size, 0);
  const done = countMarks(marks);
  const typed = Number(count);
  const validCount = count !== "" && Number.isInteger(typed) && typed >= 0;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (outline.length) save.mutate({ progress_marks: marks });
    else if (validCount) save.mutate({ progress: typed });
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle className="font-display text-2xl font-medium">
              How far did you get?
            </DialogTitle>
            <DialogDescription>
              {outline.length
                ? `Tap the last ${unit} of ${entry.item.title} you finished.`
                : `How many ${unit}s of ${entry.item.title} did you finish?`}
            </DialogDescription>
          </DialogHeader>
          <div className="mt-5 max-h-[50vh] overflow-y-auto pr-1">
            {outline.length > 0 ? (
              <>
                <Lights
                  outline={outline}
                  marks={marks}
                  unit={unit}
                  partLabel={partLabel}
                  label={`${capital(unit)}s finished`}
                  onLight={(part, number) =>
                    setMarks(fillThrough(outline, part, number))
                  }
                />
                <p
                  className="mt-4 text-sm tabular-nums text-muted-foreground"
                  aria-live="polite"
                >
                  {done} of {total} {unit}s
                </p>
              </>
            ) : (
              <div>
                <label htmlFor={inputId} className="text-sm">
                  {progress.label}
                </label>
                <Input
                  id={inputId}
                  inputMode="numeric"
                  className="mt-1 w-28"
                  value={count}
                  onChange={(event) =>
                    setCount(event.target.value.replace(/\D/g, ""))
                  }
                />
              </div>
            )}
          </div>
          <DialogFooter className="mt-6 gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Skip
            </Button>
            <Button
              type="submit"
              disabled={save.isPending || (!outline.length && !validCount)}
            >
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
