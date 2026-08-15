import type { FormatSpec } from "@/api/library";
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
 * How you hold this copy — a closed, multi-valued, per-domain vocabulary (DEC-059).
 *
 * Shared by the add screen and the opinion dialog so a format is picked the same way
 * wherever you meet it, replacing two separate rows of checkboxes.
 *
 * **It is deliberately not the shelf control.** It has no text input and no way to
 * invent a value, because a format is a fact about your copy from a list the domain
 * declares, while a shelf is a tier of organization you make up. DEC-059's rule that
 * nothing renders a format as a shelf is about that distinction, and a control that
 * offered "create" here would erase it.
 */
export function FormatPicker({
  formats,
  value,
  onChange,
  label = "Format",
}: {
  formats: readonly FormatSpec[];
  value: string[];
  onChange: (next: string[]) => void;
  label?: string;
}) {
  if (!formats.length) return null;
  const chosen = formats.filter((format) => value.includes(format.value));
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-label={label}
          className="h-11 w-auto justify-start gap-2 rounded-full bg-surface font-normal"
        >
          {chosen.length
            ? chosen.map((format) => format.label).join(", ")
            : `Choose ${label.toLowerCase()}…`}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align="start">
        <Command label={label}>
          <CommandList>
            <CommandGroup>
              {formats.map((format) => {
                const on = value.includes(format.value);
                return (
                  <CommandItem
                    key={format.value}
                    value={format.value}
                    // Multi-valued: owning a record on vinyl *and* digital is
                    // ordinary, so selecting toggles rather than replaces and the
                    // list stays open.
                    aria-selected={on}
                    onSelect={() =>
                      onChange(
                        on
                          ? value.filter((row) => row !== format.value)
                          : [...value, format.value],
                      )
                    }
                  >
                    <span className="mr-2 w-4 text-primary" aria-hidden="true">
                      {on ? "✓" : ""}
                    </span>
                    {format.label}
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
