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
 * (Sprint 108, DEC-171). It *is* the progress row of the personal region ("Episodes
 * watched 8 / 62 episodes"): opened, the lights are the one way to change the count,
 * and with no lights to draw the count is typed in the same place. Each tap is one
 * write of the whole set of marks.
 */
export function ProgressTracker({
  entry,
  types,
  icon,
}: {
  entry: LibraryEntry;
  types: ItemType[] | undefined;
  /** The row's icon, as the other personal fields carry one. */
  icon?: React.ReactNode;
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

  const value = total
    ? `${done} / ${total} ${unit}s`
    : entry.progress != null
      ? `${done} ${unit}s`
      : "—";
  // A count with no marks (imported, or typed where there were no lights) says how
  // many, not which, so it is drawn from the start until the owner changes a light;
  // saying so is what makes the first tap unsurprising.
  const imported =
    outline.length > 0 &&
    !entry.progress_marks &&
    pending === null &&
    (entry.progress ?? 0) > 0;
  const toggle = () => setOpen((value) => !value);

  return (
    <div
      data-fact="progress"
      data-progress-tracker=""
      className="group -mx-2 grid grid-cols-[9.5rem_1fr] items-center gap-x-3 rounded-md px-2 py-1.5 sm:grid-cols-[11rem_1fr]"
    >
      <dt
        onClick={toggle}
        className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground [&_svg]:h-4 [&_svg]:w-4 [&_svg]:shrink-0"
      >
        {icon}
        {progress.label}
      </dt>
      <dd
        onClick={toggle}
        className="flex min-w-0 cursor-pointer items-center justify-between gap-2"
      >
        <span className="tabular-nums">{value}</span>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={(event) => {
            event.stopPropagation();
            toggle();
          }}
          className="ml-auto flex shrink-0 items-center gap-1 rounded px-1.5 text-xs text-muted-foreground focus-ring hover:text-foreground"
        >
          {open ? "Hide" : outline.length ? `Show ${unit}s` : "Set"}
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "size-4 transition-transform motion-reduce:transition-none",
              open && "rotate-180",
            )}
          />
        </button>
      </dd>
      {open && (
        <dd id={panelId} className="col-span-2 pb-3 pt-3">
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
          {outline.length > 0 && (
            <p className="mt-3 max-w-prose text-xs text-muted-foreground">
              {partLabel && outline.length > 1
                ? `Tap one to mark it, or a ${partLabel.toLowerCase()} for all of it.`
                : "Tap one to mark it."}{" "}
              {imported
                ? `Your count of ${done} is lit from the start; change any light to say which ones.`
                : `${progress.label} counts what is lit.`}
            </p>
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
          {outline.length === 0 && (
            <SetCount entry={entry} label={progress.label} onSaved={refresh} />
          )}
        </dd>
      )}
    </div>
  );
}

/**
 * No lights to draw: the count is typed. Where lights exist they are the only way
 * to change it, so there is one control for one number.
 */
function SetCount({
  entry,
  label,
  onSaved,
}: {
  entry: LibraryEntry;
  label: string;
  onSaved: (saved: LibraryEntry) => void;
}) {
  const inputId = useId();
  const [value, setValue] = useState(
    entry.progress == null ? "" : String(entry.progress),
  );
  const set = useMutation({
    mutationFn: (count: number | null) =>
      patchEntry(entry.id, { progress: count }),
    onSuccess: onSaved,
    onError: () => toast.error("Your change could not be saved"),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    set.mutate(value === "" ? null : Number(value));
  }

  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-2">
      <div>
        <label
          htmlFor={inputId}
          className="block text-xs text-muted-foreground"
        >
          {label}
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
        variant="outline"
        disabled={set.isPending}
        className="rounded-full"
      >
        Save
      </Button>
    </form>
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
