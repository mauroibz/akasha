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
import { Button } from "@/components/ui/button";
import type { InsightKeyOption } from "@/features/library/labels";

/**
 * Which field or built-in key a ranking groups by — single-select, unlike
 * `StatusFilter`, since a ranking answers one question at a time.
 */
export function InsightsKeyPicker({
  options,
  value,
  onChange,
}: {
  options: InsightKeyOption[];
  value: string;
  onChange: (next: string) => void;
}) {
  const chosen = options.find((option) => option.name === value);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-label="Rank by"
          className="h-11 w-auto justify-start gap-2 rounded-full bg-surface font-normal"
        >
          {chosen?.label ?? "Choose a key"}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align="start">
        <Command label="Rank by">
          <CommandList>
            <CommandGroup>
              {options.map((option) => (
                <CommandItem
                  key={option.name}
                  value={option.name}
                  aria-selected={value === option.name}
                  onSelect={() => onChange(option.name)}
                >
                  <span className="mr-2 w-4 text-primary" aria-hidden="true">
                    {value === option.name ? "✓" : ""}
                  </span>
                  <span className="flex-1">{option.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
