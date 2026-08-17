import type { EntryStatus, StatusSpec } from "@/api/library";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

/**
 * Which statuses the library shows — the chosen domain's, and only its.
 *
 * It was a row of chips of its own above the library, which is a whole row of
 * chrome for the fourth of four filters. Folded in here it sits beside sort, shelf
 * and format and reads as one of them.
 *
 * **It is a popover rather than a `Select` because the filter is multi-valued**:
 * wanting *Read* and *Reading* at once is ordinary, and a `Select` can only replace.
 * That is the same reason `FormatPicker` is built this way, and this deliberately
 * copies its shape — checkmark column, list stays open on select — so the two
 * multi-select controls on the page behave identically.
 *
 * The counts come with it. They were visible on the chips at all times and are one
 * click away now; losing them entirely would have been a worse trade than the row.
 */
export function StatusFilter({
  statuses,
  counts,
  value,
  onChange,
}: {
  statuses: readonly StatusSpec[];
  counts: Partial<Record<string, number>>;
  value: EntryStatus[];
  onChange: (next: EntryStatus[]) => void;
}) {
  if (!statuses.length) return null;
  const chosen = statuses.filter((status) => value.includes(status.value));
  const label =
    chosen.length === 0
      ? "All statuses"
      : chosen.length === 1
        ? chosen[0].label
        : `${chosen.length} statuses`;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-label="Filter by status"
          className="h-11 w-auto justify-start gap-2 rounded-full bg-surface font-normal"
        >
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align="start">
        <Command label="Filter by status">
          <CommandList>
            <CommandGroup>
              {statuses.map((status) => {
                const on = value.includes(status.value);
                return (
                  <CommandItem
                    key={status.value}
                    value={status.value}
                    aria-selected={on}
                    onSelect={() =>
                      onChange(
                        on
                          ? value.filter((row) => row !== status.value)
                          : [...value, status.value],
                      )
                    }
                  >
                    <span className="mr-2 w-4 text-primary" aria-hidden="true">
                      {on ? "✓" : ""}
                    </span>
                    <span className="flex-1">{status.label}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {counts[status.value] ?? 0}
                    </span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
