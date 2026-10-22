import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import {
  fetchOutline,
  patchEntry,
  patchItem,
  type ItemType,
  type LibraryEntry,
  type ProgressMarks,
} from "@/api/library";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Lights } from "@/features/progress/Lights";
import {
  capital,
  countMarks,
  drawnMarks,
  togglePart,
  toggleMark,
} from "@/features/progress/marks";
import { outlineContext, outlineFailure } from "@/features/progress/outline";
import { cn } from "@/lib/utils";

/**
 * How far into a series or a book you got, one light per episode or chapter
 * (Sprint 108, DEC-171). Optional and quiet: a single line, closed until opened, and
 * nothing on it is required. Each tap is one write of the whole set of marks, and the
 * count beside the line follows them.
 */
export function ProgressTracker({
  entry,
  types,
}: {
  entry: LibraryEntry;
  types: ItemType[] | undefined;
}) {
  const panelId = useId();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<ProgressMarks | null>(null);
  const context = outlineContext(entry, types);

  const refresh = (saved?: LibraryEntry) => {
    if (saved) queryClient.setQueryData(queryKeys.entry(entry.id), saved);
    void queryClient.invalidateQueries({ queryKey: queryKeys.entry(entry.id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
  };
  // Taps can outrun the network. Each write sends the whole set, so only the newest
  // answer is applied, and the marks drawn stay the ones last tapped until the page's
  // own copy of the entry catches up.
  const latest = useRef(0);
  useEffect(() => setPending(null), [entry.progress_marks, entry.progress]);
  const save = useMutation({
    mutationFn: ({ marks }: { marks: ProgressMarks; seq: number }) =>
      patchEntry(entry.id, { progress_marks: marks }),
    onSuccess: (saved, { seq }) => {
      if (seq === latest.current) refresh(saved);
    },
    onError: (_error, { seq }) => {
      if (seq !== latest.current) return;
      setPending(null);
      toast.error("Your change could not be saved", {
        description: "The previous marks were restored.",
      });
    },
  });
  const load = useMutation({
    mutationFn: () => fetchOutline(entry.item.id),
    onSuccess: () => refresh(),
  });

  if (!context) return null;
  const { progress, outline, partLabel, partsMissing, totalField } = context;
  const unit = progress.unit_label;
  const units = `${capital(unit)}s`;
  const marks =
    pending ?? drawnMarks(entry.progress_marks, entry.progress, outline);
  const total = outline.reduce((sum, part) => sum + part.size, 0);
  const done = outline.length ? countMarks(marks) : (entry.progress ?? 0);
  const write = (next: ProgressMarks) => {
    latest.current += 1;
    setPending(next);
    save.mutate({ marks: next, seq: latest.current });
  };

  return (
    <div data-progress-tracker="" className="mt-2 border-t border-border pt-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-11 w-full items-center gap-2 rounded-md text-left text-sm focus-ring"
      >
        <span className="font-medium text-foreground">{units}</span>
        <span className="text-muted-foreground" aria-hidden="true">
          ·
        </span>
        <span className="tabular-nums text-muted-foreground">
          {total ? `${done} of ${total}` : done ? `${done}` : "not counted"}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "ml-auto size-4 text-muted-foreground transition-transform motion-reduce:transition-none",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div id={panelId} className="pb-3 pt-2">
          {outline.length > 0 && (
            <Lights
              outline={outline}
              marks={marks}
              unit={unit}
              partLabel={partLabel}
              label={`${units}: ${done} of ${total}`}
              onLight={(part, number) => write(toggleMark(marks, part, number))}
              onPart={(part) => write(togglePart(marks, part))}
            />
          )}
          {partsMissing && (
            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              <Button
                variant="outline"
                size="sm"
                className="rounded-full"
                disabled={load.isPending}
                onClick={() => load.mutate()}
              >
                {load.isPending ? "Looking…" : `Load the ${unit} list`}
              </Button>
              {load.error && (
                <span role="status" className="text-muted-foreground">
                  {outlineFailure(load.error, unit)}
                </span>
              )}
            </div>
          )}
          {totalField && (
            <AddTotal
              itemId={entry.item.id}
              field={totalField}
              unit={unit}
              onSaved={() => refresh()}
            />
          )}
          {outline.length > 0 && (
            <p className="mt-3 text-xs text-muted-foreground">
              {partLabel && outline.length > 1
                ? `Tap a ${unit}, or a ${partLabel.toLowerCase()} for all of it.`
                : `Tap a ${unit} to mark it.`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** No outline and nothing to fetch: the owner types how many (a book's chapters). */
function AddTotal({
  itemId,
  field,
  unit,
  onSaved,
}: {
  itemId: number;
  field: string;
  unit: string;
  onSaved: () => void;
}) {
  const inputId = useId();
  const [value, setValue] = useState("");
  const add = useMutation({
    mutationFn: (count: number) =>
      patchItem(itemId, { metadata: { [field]: count } }),
    onSuccess: onSaved,
    onError: () => toast.error(`The ${unit} count could not be saved`),
  });
  const count = Number(value);
  const valid = Number.isInteger(count) && count >= 1 && count <= 2000;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid) add.mutate(count);
  }

  return (
    <form onSubmit={submit} className="mt-1 flex flex-wrap items-end gap-2">
      <div>
        <label
          htmlFor={inputId}
          className="block text-xs text-muted-foreground"
        >
          How many {unit}s?
        </label>
        <Input
          id={inputId}
          inputMode="numeric"
          className="mt-1 h-9 w-24"
          value={value}
          onChange={(event) => setValue(event.target.value.replace(/\D/g, ""))}
        />
      </div>
      <Button
        type="submit"
        size="sm"
        disabled={!valid || add.isPending}
        className="rounded-full"
      >
        Add {unit}s
      </Button>
    </form>
  );
}
