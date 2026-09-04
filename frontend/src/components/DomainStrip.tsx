import { cn } from "@/lib/utils";

export interface DomainStripOption {
  id: string;
  label: string;
}

export interface DomainStripProps {
  domains: ReadonlyArray<DomainStripOption>;
  value: string;
  onChange: (id: string) => void;
  className?: string;
}

/**
 * One domain strip (proposal §3.3, finding 9), extracted from the library's and
 * insights' near-identical radiogroups — the same markup down to the class list,
 * both `shrink-0`, and both able to overflow a 390px viewport by about 39px with
 * five real domains (DEC-134, measured on `/insights`; `/` had the same markup and
 * had never been measured).
 *
 * The fix is structural rather than cosmetic: the strip scrolls within its own box
 * (`overflow-x-auto`, `min-w-0`, `max-w-full`) instead of refusing to shrink
 * (`shrink-0` on the row) and pushing the document sideways. This pays DEC-134's
 * outstanding defect once, for both screens that render it.
 */
export function DomainStrip({
  domains,
  value,
  onChange,
  className,
}: DomainStripProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Choose a domain"
      className={cn(
        "flex min-w-0 max-w-full gap-0.5 overflow-x-auto rounded-full bg-surface p-1",
        className,
      )}
    >
      {domains.map((choice) => (
        <button
          key={choice.id}
          type="button"
          role="radio"
          aria-checked={value === choice.id}
          className={cn(
            "min-h-11 shrink-0 rounded-full px-5 py-2 text-sm font-medium transition-colors focus-ring",
            value === choice.id
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
          onClick={() => onChange(choice.id)}
        >
          {choice.label}
        </button>
      ))}
    </div>
  );
}
