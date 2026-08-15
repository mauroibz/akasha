import { useState } from "react";

import type { ShelfWithCount } from "@/api/shelves";
import type { Shelf } from "@/api/library";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

interface ShelfPickerProps {
  /** The shelves this entry is on. */
  current: Shelf[];
  /** Every shelf that exists, for the list to filter. */
  available: ShelfWithCount[];
  /** Assign the entry to exactly these shelves. */
  onChange: (shelfIds: number[]) => Promise<void>;
  /** Create a shelf by this name and return it, so it can be assigned at once. */
  onCreate: (name: string) => Promise<Shelf>;
}

/**
 * Shelf membership, where the book is.
 *
 * The owner's report was about *distance*: shelf membership lived inside a dialog
 * named after something else, and creating a shelf was a whole route. So this is
 * one control that does both — the same input filters what exists and offers to
 * create what does not — sitting on the page beside the shelves it edits.
 *
 * It is deliberately not a format control. Formats are a closed per-domain
 * vocabulary you pick from; shelves are yours and you invent them (DEC-059), and
 * the two must not converge into one widget that does both badly.
 *
 * Shared by the detail page and the add screen. It owns no fetching of its own —
 * both the assignment and the creation are the caller's, so the add screen can hold
 * the choice in local state until the entry it belongs to exists.
 */
export function ShelfPicker({
  current,
  available,
  onChange,
  onCreate,
}: ShelfPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const on = new Set(current.map((shelf) => shelf.id));
  const typed = query.trim();
  const offered = available.filter((shelf) => !on.has(shelf.id));
  // Only when nothing already carries that exact name, so the list never offers to
  // create a duplicate of the row directly above it.
  const canCreate =
    typed.length > 0 &&
    !available.some(
      (shelf) => shelf.name.toLowerCase() === typed.toLowerCase(),
    );

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
      setQuery("");
      setOpen(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2" data-shelf-picker="">
      {current.map((shelf) => (
        <span
          key={shelf.id}
          className="inline-flex items-center gap-1 rounded-full border border-border py-0.5 pl-3 pr-1 text-sm"
        >
          {shelf.name}
          <button
            type="button"
            // Named for the shelf, so a screen reader hears which one this drops
            // rather than one of several identical "Remove" buttons.
            aria-label={`Remove from ${shelf.name}`}
            className="rounded-full px-1.5 text-muted-foreground hover:text-foreground focus-ring"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await onChange(
                  current
                    .filter((row) => row.id !== shelf.id)
                    .map((row) => row.id),
                );
              })
            }
          >
            ×
          </button>
        </span>
      ))}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className="rounded-full"
            disabled={busy}
          >
            Add to a shelf
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-64 p-0" align="start">
          <Command
            // The input's accessible name. It has to be given here rather than as
            // an `aria-label` on the input, because cmdk points the input's
            // `aria-labelledby` at the element this prop renders — and that wins.
            label="Find or create a shelf"
            // The list is already narrowed to shelves this entry is not on, and
            // cmdk's own scoring would additionally reorder and hide rows behind
            // the create option. Filtering here keeps "what you typed" and "what
            // is offered" the same thing.
            shouldFilter={false}
          >
            <CommandInput
              placeholder="Find or create a shelf…"
              value={query}
              onValueChange={setQuery}
            />
            <CommandList>
              {!canCreate && offered.length === 0 && (
                <CommandEmpty>No shelves to add.</CommandEmpty>
              )}
              <CommandGroup>
                {offered
                  .filter((shelf) =>
                    shelf.name.toLowerCase().includes(typed.toLowerCase()),
                  )
                  .map((shelf) => (
                    <CommandItem
                      key={shelf.id}
                      value={shelf.name}
                      onSelect={() =>
                        void run(async () => {
                          await onChange([
                            ...current.map((r) => r.id),
                            shelf.id,
                          ]);
                        })
                      }
                    >
                      {shelf.name}
                    </CommandItem>
                  ))}
                {canCreate && (
                  <CommandItem
                    value={`__create__${typed}`}
                    onSelect={() =>
                      void run(async () => {
                        // Create then assign, in that order and without a second
                        // trip through the UI: "create it and put this on it" is
                        // one intention, so it is one action.
                        const created = await onCreate(typed);
                        await onChange([
                          ...current.map((row) => row.id),
                          created.id,
                        ]);
                      })
                    }
                  >
                    Create “{typed}”
                  </CommandItem>
                )}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
