import { cn } from "@/lib/utils";

export interface DomainStripOption {
  id: string;
  label: string;
}

export interface DomainStripProps {
  domains: ReadonlyArray<DomainStripOption>;
  value: string;
  onChange: (id: string) => void;
  /** What is being chosen, when it is not the screen's medium: the bar's web search. */
  label?: string;
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
 *
 * One drawing since Sprint 139 (DEC-193): underlined tabs, the chosen one marked in
 * the accent. The filled pills the Library drew and the hand-written tabs on
 * Insights and Shelves were the same control with two looks.
 */
export function DomainStrip({
  domains,
  value,
  onChange,
  label = "Choose a domain",
  className,
}: DomainStripProps) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn("flex min-w-0 max-w-full gap-6 overflow-x-auto", className)}
    >
      {domains.map((choice) => (
        <button
          key={choice.id}
          type="button"
          role="radio"
          aria-checked={value === choice.id}
          className={cn(
            "min-h-11 shrink-0 border-b-2 px-0.5 text-[15px] font-medium transition-colors focus-ring",
            value === choice.id
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
          onClick={() => onChange(choice.id)}
        >
          {choice.label}
        </button>
      ))}
    </div>
  );
}
