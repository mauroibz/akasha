import { GripVertical, X } from "lucide-react";

import type { ModuleLayout, ModuleSize } from "@/api/home";
import { cn } from "@/lib/utils";

import { labelOf } from "./layout";
import type { Arrange } from "./useArrange";

const sizes: Array<{ value: ModuleSize; label: string }> = [
  { value: "S", label: "Small" },
  { value: "M", label: "Medium" },
  { value: "L", label: "Large" },
];

/** The strip above a showcase while arranging: its handle, its size, and remove. */
export function ArrangeControls({
  row,
  arrange,
}: {
  row: ModuleLayout;
  arrange: Arrange;
}) {
  const label = labelOf(row);
  return (
    <div className="mb-1.5 flex items-center gap-1">
      <button
        type="button"
        aria-label={`Move ${label}`}
        {...arrange.handle(row.module)}
        className={cn(
          "flex h-11 w-11 shrink-0 cursor-grab touch-none items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground focus-ring",
          arrange.dragging === row.module && "cursor-grabbing text-foreground",
        )}
      >
        <GripVertical className="h-4 w-4" aria-hidden="true" />
      </button>
      <span className="min-w-0 flex-1 truncate text-sm font-medium">
        {label}
      </span>
      <div
        role="group"
        aria-label={`Size of ${label}`}
        className="flex shrink-0 gap-0.5"
      >
        {sizes.map((size) => (
          <button
            key={size.value}
            type="button"
            aria-label={size.label}
            aria-pressed={row.size === size.value}
            onClick={() => arrange.resize(row.module, size.value)}
            className="h-9 w-9 rounded-md text-xs font-semibold text-muted-foreground hover:text-foreground focus-ring aria-pressed:bg-primary aria-pressed:text-primary-foreground"
          >
            {size.value}
          </button>
        ))}
      </div>
      <button
        type="button"
        aria-label={`Remove ${label}`}
        onClick={() => arrange.remove(row.module)}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground focus-ring"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

const groups: Array<{ title: string; test: (module: string) => boolean }> = [
  { title: "Showcases", test: (module) => !module.includes(":") },
  { title: "A year", test: (module) => module.startsWith("year:") },
  { title: "A shelf", test: (module) => module.startsWith("shelf:") },
  {
    title: "A number from Insights",
    test: (module) => module.startsWith("insight:"),
  },
];

/** What can be added, by kind; and the way back to the default. */
export function ArrangeTray({
  layout,
  arrange,
  onReset,
  onDone,
}: {
  layout: ModuleLayout[];
  arrange: Arrange;
  onReset: () => void;
  onDone: () => void;
}) {
  const hidden = layout.filter((row) => row.hidden);
  return (
    <section
      aria-label="Add a showcase"
      className="rounded-xl border border-dashed border-border p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="font-display text-lg font-medium">Add a showcase</h3>
        <div className="flex gap-4 text-sm">
          <button
            type="button"
            onClick={onReset}
            className="min-h-11 text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-ring"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={onDone}
            className="min-h-11 rounded-full bg-primary px-5 font-semibold text-primary-foreground focus-ring"
          >
            Done
          </button>
        </div>
      </div>
      {hidden.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          Everything there is to show is already placed.
        </p>
      ) : (
        groups.map((group) => {
          const rows = hidden.filter((row) => group.test(row.module));
          if (rows.length === 0) return null;
          return (
            <div key={group.title} className="mt-3">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {group.title}
              </p>
              <ul className="mt-1.5 flex flex-wrap gap-2">
                {rows.map((row) => (
                  <li key={row.module}>
                    <button
                      type="button"
                      aria-label={`Add ${labelOf(row)}`}
                      onClick={() => arrange.add(row.module)}
                      className="min-h-11 rounded-full border border-border bg-surface px-3.5 text-sm font-medium hover:bg-accent focus-ring"
                    >
                      {labelOf(row)
                        .replace(/^Shelf: /, "")
                        .replace(/ this year$/, "")}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          );
        })
      )}
      <p role="status" className="sr-only">
        {arrange.announcement}
      </p>
    </section>
  );
}
