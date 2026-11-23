import { GripVertical } from "lucide-react";
import { useEffect, useRef, useState, type PointerEvent } from "react";

import type { ModuleLayout, ModuleSize } from "@/api/home";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

import { labelOf as nameOf } from "./layout";

const sizes: Array<{ value: ModuleSize; label: string }> = [
  { value: "S", label: "Small" },
  { value: "M", label: "Medium" },
  { value: "L", label: "Large" },
];

function moved(
  layout: ModuleLayout[],
  module: string,
  to: number,
): ModuleLayout[] {
  const row = layout.find((item) => item.module === module);
  if (!row) return layout;
  const rest = layout.filter((item) => item.module !== module);
  const place = Math.max(0, Math.min(rest.length, to));
  return [...rest.slice(0, place), row, ...rest.slice(place)];
}

/**
 * *Edit home* (Sprint 131, DEC-183, the mockup's *On the phone, and editing*): each
 * module in order, with a handle to drag (or, focused, the up and down arrows), a
 * size and a switch to hide it. Every change is handed to `onChange` at once, so it
 * is stored as it is made; *Reset* hands back the default.
 *
 * The drag is pointer events on the handle rather than a library, as the tier board
 * moves covers with its own taps and keys: one gesture for a mouse and a finger.
 */
export function EditHome({
  open,
  onOpenChange,
  layout,
  defaults,
  onChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  layout: ModuleLayout[];
  defaults: ModuleLayout[];
  onChange: (next: ModuleLayout[]) => void;
}) {
  const rows = useRef(new Map<string, HTMLLIElement>());
  const handles = useRef(new Map<string, HTMLButtonElement>());
  const focusAfter = useRef<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [preview, setPreview] = useState<ModuleLayout[] | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const shown = preview ?? layout;
  const labelOf = (module: string) =>
    nameOf(layout.find((row) => row.module === module) ?? { module });
  // What the last change made, before the parent has rendered it back: two arrow
  // presses in quick succession must move twice, not twice from the same place.
  // Taken from the prop only when the prop itself changes, so a render of this
  // panel alone (an announcement) cannot put an older layout back.
  const latest = useRef(layout);
  const received = useRef(layout);
  if (received.current !== layout) {
    received.current = layout;
    latest.current = layout;
  }
  const commit = (next: ModuleLayout[]) => {
    latest.current = next;
    onChange(next);
  };

  useEffect(() => {
    if (!focusAfter.current) return;
    handles.current.get(focusAfter.current)?.focus();
    focusAfter.current = null;
  });

  const change = (module: string, patch: Partial<ModuleLayout>) =>
    commit(
      latest.current.map((row) =>
        row.module === module ? { ...row, ...patch } : row,
      ),
    );

  const moveBy = (module: string, step: number) => {
    const current = latest.current;
    const from = current.findIndex((row) => row.module === module);
    const to = from + step;
    if (from < 0 || to < 0 || to >= current.length) return;
    focusAfter.current = module;
    commit(moved(current, module, to));
    setAnnouncement(
      `${labelOf(module)} moved to ${to + 1} of ${current.length}`,
    );
  };

  const onPointerDown = (
    event: PointerEvent<HTMLButtonElement>,
    module: string,
  ) => {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setDragging(module);
    setPreview(layout);
  };

  const onPointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    if (!dragging || !preview) return;
    const others = preview.filter((row) => row.module !== dragging);
    let place = 0;
    for (const row of others) {
      const box = rows.current.get(row.module)?.getBoundingClientRect();
      if (box && event.clientY > box.top + box.height / 2) place += 1;
    }
    const next = moved(preview, dragging, place);
    if (next.some((row, index) => row.module !== preview[index].module))
      setPreview(next);
  };

  const onPointerUp = () => {
    if (!dragging) return;
    const next = preview;
    setDragging(null);
    setPreview(null);
    if (
      next &&
      next.some((row, index) => row.module !== layout[index]?.module)
    ) {
      commit(next);
      const to = next.findIndex((row) => row.module === dragging);
      setAnnouncement(
        `${labelOf(dragging)} moved to ${to + 1} of ${next.length}`,
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-display text-xl font-medium">
            Edit home
          </DialogTitle>
          <DialogDescription>
            Drag a handle, or focus it and use the up and down arrows, to change
            the order. On a phone every module is full width and its size only
            changes how much it shows.
          </DialogDescription>
        </DialogHeader>
        <ul aria-label="Modules" className="space-y-1.5">
          {shown.map((row) => {
            const label = labelOf(row.module);
            return (
              <li
                key={row.module}
                data-module={row.module}
                ref={(node) => {
                  if (node) rows.current.set(row.module, node);
                  else rows.current.delete(row.module);
                }}
                className={cn(
                  "flex min-h-12 items-center gap-2 rounded-lg border border-border bg-surface px-2 py-1.5",
                  dragging === row.module && "border-primary shadow-md",
                  row.hidden && "text-muted-foreground",
                )}
              >
                <button
                  type="button"
                  aria-label={`Move ${label}`}
                  ref={(node) => {
                    if (node) handles.current.set(row.module, node);
                    else handles.current.delete(row.module);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                      event.preventDefault();
                      moveBy(row.module, event.key === "ArrowUp" ? -1 : 1);
                    }
                  }}
                  onPointerDown={(event) => onPointerDown(event, row.module)}
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                  onPointerCancel={onPointerUp}
                  className="flex h-10 w-8 shrink-0 cursor-grab touch-none items-center justify-center rounded text-muted-foreground hover:bg-accent focus-ring active:cursor-grabbing"
                >
                  <GripVertical className="h-4 w-4" aria-hidden="true" />
                </button>
                <span className="min-w-0 flex-1 truncate text-sm font-medium">
                  {label}
                </span>
                {
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
                        onClick={() => change(row.module, { size: size.value })}
                        className={cn(
                          "h-9 w-9 rounded-md text-xs font-semibold transition-colors focus-ring",
                          row.size === size.value
                            ? "bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:bg-accent",
                        )}
                      >
                        {size.value}
                      </button>
                    ))}
                  </div>
                }
                <button
                  type="button"
                  role="switch"
                  aria-checked={!row.hidden}
                  aria-label={`Show ${label}`}
                  onClick={() => change(row.module, { hidden: !row.hidden })}
                  className={cn(
                    "relative h-6 w-11 shrink-0 rounded-full transition-colors focus-ring",
                    row.hidden ? "bg-muted" : "bg-primary",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute top-1 h-4 w-4 rounded-full bg-background shadow transition-[left]",
                      row.hidden ? "left-1" : "left-6",
                    )}
                  />
                </button>
              </li>
            );
          })}
        </ul>
        <p role="status" className="sr-only">
          {announcement}
        </p>
        <div className="flex justify-between gap-3">
          <button
            type="button"
            onClick={() => {
              commit(defaults.map((row) => ({ ...row })));
              setAnnouncement("Home is back to its default layout");
            }}
            className="inline-flex min-h-11 items-center rounded-full border border-border px-5 text-sm font-medium transition-colors hover:bg-accent focus-ring"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="inline-flex min-h-11 items-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground focus-ring"
          >
            Done
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
