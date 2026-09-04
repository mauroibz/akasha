import type { ReactNode, Ref } from "react";

import { BackToLibrary } from "@/components/BackToLibrary";
import { cn } from "@/lib/utils";

export interface PageHeaderProps {
  /** A leading mark or icon, beside the eyebrow/title stack (the Library lockup). */
  icon?: ReactNode;
  eyebrow?: ReactNode;
  title: ReactNode;
  headingRef?: Ref<HTMLHeadingElement>;
  /** A number or short phrase beside the title, at reduced weight. */
  count?: ReactNode;
  lede?: ReactNode;
  actions?: ReactNode;
  /** Renders the one "← Library" control above the header (finding 8). */
  back?: boolean;
  className?: string;
}

/**
 * One page header (proposal §3.2): eyebrow, title, optional count, lede, an
 * actions slot — on every screen, including `AddPage`, which had none at all.
 *
 * Before this there were three header treatments (the brand lockup on Library and
 * Triage, a plain title-and-lede on Insights, a title with no lockup on Import) and
 * four spellings of the way back (finding 8). This is the one, and `back` renders
 * it in the one place it now lives.
 */
export function PageHeader({
  icon,
  eyebrow,
  title,
  headingRef,
  count,
  lede,
  actions,
  back = false,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("border-b border-border pb-6", className)}>
      {back && <BackToLibrary className="mb-4" />}
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div className={icon ? "flex items-center gap-4" : undefined}>
          {icon}
          <div>
            {eyebrow !== undefined && (
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">
                {eyebrow}
              </p>
            )}
            <h1
              ref={headingRef}
              tabIndex={headingRef ? -1 : undefined}
              className={cn(
                "text-4xl font-semibold tracking-tight",
                headingRef && "focus:outline-none",
                eyebrow !== undefined && "mt-2",
              )}
            >
              {title}
              {count !== undefined && (
                <span className="ml-3 text-lg text-muted-foreground">
                  {count}
                </span>
              )}
            </h1>
            {lede !== undefined && (
              <p className="mt-2 text-muted-foreground">{lede}</p>
            )}
          </div>
        </div>
        {actions !== undefined && (
          <div className="flex items-center gap-3">{actions}</div>
        )}
      </div>
    </header>
  );
}
