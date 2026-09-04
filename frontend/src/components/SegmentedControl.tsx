import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string> {
  value: T;
  label: React.ReactNode;
  /** The button's accessible name, when the visible label alone would not do. */
  ariaLabel?: string;
}

export interface SegmentedControlProps<T extends string> {
  ariaLabel: string;
  value: T;
  onChange: (value: T) => void;
  options: ReadonlyArray<SegmentedOption<T>>;
  className?: string;
}

/**
 * One segmented control (proposal §3.3, finding 10), extracted from the library's
 * *Grid / Table* toggle and insights' *Most collected / Best rated* toggle —
 * `flex rounded-full bg-surface p-1` around `aria-pressed` buttons in both places,
 * differing only in that one of the two carried the 44px target both should have
 * had. Every option gets it now.
 */
export function SegmentedControl<T extends string>({
  ariaLabel,
  value,
  onChange,
  options,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn("flex rounded-full bg-surface p-1", className)}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          aria-label={option.ariaLabel}
          className="min-h-11 rounded-full px-4 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-ring aria-pressed:bg-surface-raised aria-pressed:text-foreground"
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
