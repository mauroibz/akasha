import type { Ref } from "react";

import type { EntryStatus, StatusSpec } from "@/api/library";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fallbackStatuses } from "@/features/library/labels";
import { cn } from "@/lib/utils";

interface StatusSelectProps {
  value: EntryStatus;
  /** The statuses of the item's domain; defaults to the shared vocabulary. */
  statuses?: readonly StatusSpec[];
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
 *
 * It has no list of its own: the statuses arrive from the item's domain, so an
 * album offers `Owned` and a book offers `Read` with no branch here (seam 5b).
 */
export function StatusSelect({
  value,
  onValueChange,
  label,
  statuses = fallbackStatuses,
  className,
  triggerRef,
}: StatusSelectProps) {
  // Declared order, except that the inbox sinks to the bottom in every domain:
  // it is where imports land rather than something a reader picks, so it should
  // not be the first thing an open list offers.
  const ordered = [
    ...statuses.filter((status) => status.choosable),
    ...statuses.filter((status) => !status.choosable),
  ];
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
        {ordered.map((status) => (
          <SelectItem key={status.value} value={status.value}>
            {status.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
