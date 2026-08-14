import type { Ref } from "react";

import type { EntryStatus } from "@/api/library";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { statusLabels } from "@/features/library/labels";
import { cn } from "@/lib/utils";

const orderedStatuses: readonly EntryStatus[] = [
  "read",
  "reading",
  "to_read",
  "wishlist",
  "dropped",
  "unsorted",
];

interface StatusSelectProps {
  value: EntryStatus;
  /** The labels of the item's domain; defaults to the shared vocabulary. */
  labels?: Record<EntryStatus, string>;
  onValueChange: (status: EntryStatus) => void;
  /** Accessible name. Radix has no implicit label, so this is required. */
  label: string;
  className?: string;
  /** The trigger, for screens that move focus here after another action. */
  triggerRef?: Ref<HTMLButtonElement>;
}

/**
 * The one status control, used by the library card, the detail form, and the
 * add form. Radix renders it as `button[role="combobox"]` with a listbox
 * portalled to `document.body` — which is why `isEditableTarget` guards on the
 * role rather than on tag names.
 */
export function StatusSelect({
  value,
  onValueChange,
  label,
  labels = statusLabels,
  className,
  triggerRef,
}: StatusSelectProps) {
  return (
    <Select
      value={value}
      onValueChange={(next) => onValueChange(next as EntryStatus)}
    >
      <SelectTrigger
        ref={triggerRef}
        aria-label={label}
        className={cn("h-11", className)}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {orderedStatuses.map((status) => (
          <SelectItem key={status} value={status}>
            {labels[status]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
