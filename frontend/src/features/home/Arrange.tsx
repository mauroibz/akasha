import { GripVertical, X } from "lucide-react";

import type { ModuleLayout, ModuleSize } from "@/api/home";
import { cn } from "@/lib/utils";

import { fullWidth, labelOf } from "./layout";
import type { Arrange } from "./useArrange";

const sizes: Array<{ value: ModuleSize; label: string }> = [
  { value: "S", label: "Small" },
  { value: "M", label: "Medium" },
  { value: "L", label: "Large" },
];

/** The strip above a placed thing while personalizing: its handle, its size, and remove. */
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
        // A band is always the whole row: its size is not the person's to set.
        hidden={fullWidth.has(row.module)}
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
