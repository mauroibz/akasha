import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { getHomePreview, type ModuleLayout, type ModuleSize } from "@/api/home";
import type { ItemType } from "@/api/library";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { YourMedia } from "@/features/media/YourMedia";
import { ThemePicker } from "@/features/theme/ThemePicker";
import { cn } from "@/lib/utils";

import { hasContent } from "./content";
import { fullWidth, labelOf } from "./layout";
import { Showcase } from "./Showcase";

const groups: Array<{ title: string; test: (module: string) => boolean }> = [
  { title: "The library", test: (module) => !module.includes(":") },
  { title: "A year", test: (module) => module.startsWith("year:") },
  { title: "A shelf", test: (module) => module.startsWith("shelf:") },
  {
    title: "A number from the Journal",
    test: (module) => module.startsWith("insight:"),
  },
];

const sizes: Array<{ value: ModuleSize; label: string }> = [
  { value: "S", label: "Small" },
  { value: "M", label: "Medium" },
  { value: "L", label: "Large" },
];

const quiet =
  "min-h-11 rounded-full border border-border bg-surface px-4 text-sm font-medium hover:bg-accent focus-ring";

/**
 * The bar that is on screen while personalizing (Sprint 150, DEC-195): what belongs
 * to the whole front rather than to one thing on it. *Your media* and *Theme* open
 * as dialogs, so the page under the bar holds only what is placed. The owner on the
 * tray this replaces: "hard to tell what's contextual vs what's on there".
 */
export function PersonalizeBar({
  onReset,
  onDone,
  announcement,
}: {
  onReset: () => void;
  onDone: () => void;
  announcement: string;
}) {
  const [open, setOpen] = useState<"media" | "theme" | null>(null);
  return (
    <div
      role="toolbar"
      aria-label="Personalize"
      className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/50 bg-primary/10 px-3 py-2"
    >
      <p className="mr-auto text-sm">
        <span className="font-semibold">Personalizing.</span>{" "}
        <span className="text-muted-foreground">
          Drag a handle to move, or add with the plus.
        </span>
      </p>
      <button type="button" className={quiet} onClick={() => setOpen("media")}>
        Your media
      </button>
      <button type="button" className={quiet} onClick={() => setOpen("theme")}>
        Theme
      </button>
      <button type="button" className={quiet} onClick={onReset}>
        Reset
      </button>
      <button
        type="button"
        onClick={onDone}
        className="min-h-11 rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground focus-ring"
      >
        Done
      </button>
      <Dialog
        open={open !== null}
        onOpenChange={(next) => !next && setOpen(null)}
      >
        <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl font-medium">
              {open === "theme" ? "Theme" : "Your media"}
            </DialogTitle>
            <DialogDescription>
              {open === "theme"
                ? "Applied at once, and kept in this browser."
                : "Which media you keep, and in what order."}
            </DialogDescription>
          </DialogHeader>
          {open === "theme" ? (
            <ThemePicker compact />
          ) : (
            <YourMedia heading={false} />
          )}
        </DialogContent>
      </Dialog>
      <p role="status" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}

/** The blank square with a plus: the one way to add, where the next thing would go. */
export function AddTile({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Add to your library's front"
      className="flex min-h-40 w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border text-muted-foreground transition-colors hover:border-primary hover:text-foreground focus-ring"
    >
      <Plus className="h-7 w-7" aria-hidden="true" />
      <span className="text-sm font-medium">Add</span>
    </button>
  );
}

/**
 * Choosing what to add (Sprint 150, DEC-195): a list on one side, the chosen one's
 * real preview on the other, drawn by the component that will stand on the page
 * from `GET /api/home/preview`, then *Add*. Nothing is placed by looking.
 */
export function AddDialog({
  open,
  onOpenChange,
  layout,
  types,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  layout: ModuleLayout[];
  types: ItemType[] | undefined;
  onAdd: (module: string, size: ModuleSize) => void;
}) {
  const hidden = layout.filter((row) => row.hidden);
  const [picked, setPicked] = useState<string | null>(null);
  const [size, setSize] = useState<ModuleSize | null>(null);
  const row = hidden.find((item) => item.module === picked) ?? hidden[0];
  const chosenSize = size ?? row?.size ?? "M";
  const preview = useQuery({
    queryKey: ["home-preview", row?.module],
    queryFn: ({ signal }) => getHomePreview(row!.module, signal),
    enabled: open && Boolean(row),
    retry: false,
    staleTime: 30_000,
  });
  const choose = (module: string) => {
    setPicked(module);
    setSize(null);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-medium">
            Add to your library
          </DialogTitle>
          <DialogDescription>
            Choose one to see it as it would stand, then add it.
          </DialogDescription>
        </DialogHeader>
        {!row ? (
          <p className="text-sm text-muted-foreground">
            Everything there is to show is already placed.
          </p>
        ) : (
          <div className="grid gap-5 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]">
            <div
              role="radiogroup"
              aria-label="What to add"
              className="max-h-[50dvh] space-y-3 overflow-y-auto pr-1 md:max-h-[60dvh]"
            >
              {groups.map((group) => {
                const rows = hidden.filter((item) => group.test(item.module));
                if (rows.length === 0) return null;
                return (
                  <div key={group.title}>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      {group.title}
                    </p>
                    <div className="mt-1">
                      {rows.map((item) => (
                        <button
                          key={item.module}
                          type="button"
                          role="radio"
                          aria-checked={item.module === row.module}
                          onClick={() => choose(item.module)}
                          className={cn(
                            "flex min-h-11 w-full items-center rounded-lg px-3 text-left text-sm focus-ring",
                            item.module === row.module
                              ? "bg-primary/15 font-semibold"
                              : "hover:bg-accent",
                          )}
                        >
                          {labelOf(item).replace(/^Shelf: /, "")}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="min-w-0">
              <div
                role="region"
                aria-label={`Preview of ${labelOf(row)}`}
                // What is inside is a picture of the thing, not the thing: its
                // buttons and links are not for use here.
                {...({ inert: "" } as object)}
                className="pointer-events-none min-h-40 rounded-xl bg-background p-3"
              >
                {preview.data && hasContent(row.module, preview.data) ? (
                  <Showcase
                    moduleKey={row.module}
                    size={chosenSize}
                    label={labelOf(row)}
                    data={preview.data}
                    types={types}
                  />
                ) : (
                  <p className="p-4 text-sm text-muted-foreground">
                    {preview.isPending
                      ? "Drawing it…"
                      : preview.isError
                        ? "It could not be drawn just now; it can still be added."
                        : "Nothing to show in it yet. It appears on the page when it has something."}
                  </p>
                )}
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                {!fullWidth.has(row.module) && (
                  <div
                    role="group"
                    aria-label="Size"
                    className="flex rounded-full bg-muted p-0.5"
                  >
                    {sizes.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        aria-pressed={chosenSize === option.value}
                        onClick={() => setSize(option.value)}
                        className="min-h-11 rounded-full px-4 text-sm font-medium text-muted-foreground focus-ring aria-pressed:bg-surface-raised aria-pressed:text-foreground"
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => {
                    onAdd(row.module, chosenSize);
                    setPicked(null);
                    setSize(null);
                    onOpenChange(false);
                  }}
                  className="ml-auto min-h-11 rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground focus-ring"
                >
                  Add {labelOf(row).replace(/^Shelf: /, "")}
                </button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
