import type { InsightRow } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import type { Superlative } from "@/features/library/insights";
import { meanScoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

// "Holds the most" rather than "Most collected": the sort-order toggle beside
// it already reads "Most collected", and the two are not the same fact -- the
// toggle names how the cards below are ordered, this names one row.
const titles: Record<Superlative["kind"], string> = {
  most_collected: "Holds the most",
  highest_rated: "Highest rated",
  steadiest: "Steadiest",
};

/** What each superlative says, beside its label. */
function stat(superlative: Superlative) {
  const { kind, row } = superlative;
  if (kind === "most_collected") {
    return (
      <span className="text-sm tabular-nums text-muted-foreground">
        {row.count} {row.count === 1 ? "entry" : "entries"}
      </span>
    );
  }
  if (kind === "highest_rated") {
    return (
      <span
        className={cn(
          "text-sm",
          scoreChipShape,
          meanScoreChipClass(row.mean_score),
        )}
      >
        {row.mean_score?.toFixed(1)}
      </span>
    );
  }
  return (
    <span className="text-sm tabular-nums text-muted-foreground">
      ±{row.score_spread?.toFixed(1)}
    </span>
  );
}

/**
 * The leading key, promoted: its top row drawn large, and the three answers
 * about it beside — most collected, highest rated, steadiest (Sprint 067,
 * proposal §2.7; Sprint 073 deliverable 1 folded them into the hero so a
 * page-level strip could stop repeating the card under it, finding 9). Fewer
 * than three tiles when the library cannot honestly support them
 * (`computeSuperlatives`), and nothing at all for a library with no ranking.
 *
 * One component rather than a block each card copies: `InsightsCard` and
 * `ChronologyCard` had byte-identical promoted rows, and either could drift
 * from the other while both call themselves the hero.
 *
 * *Beside*, not below, is the point of the layout. The hero spans all twelve
 * columns for weight (deliverable 5), so at desktop widths a promoted block of
 * a thumbnail and three short lines left a thousand empty pixels to its right
 * with the superlatives stacked underneath in their own row. They share the
 * row now and wrap onto their own line only when the width genuinely runs out.
 */
export function HeroSummary({
  top,
  superlatives,
  totalEntries,
  ratedEntries,
}: {
  /** The leading key's own top row, by whichever order is active. */
  top: InsightRow | undefined;
  superlatives: Superlative[];
  totalEntries: number;
  ratedEntries: number;
}) {
  if (!top && superlatives.length === 0) return null;

  return (
    <div className="px-4 pb-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
        {top && (
          // Capped rather than free: past `max-w-sm` a cover and three short
          // lines only get further apart, and the width is worth more to the
          // tiles beside them.
          <div className="flex min-w-[11rem] max-w-sm flex-1 items-center gap-4">
            <CoverImage
              src={top.covers[0]}
              alt=""
              className="h-24 w-16 shrink-0 object-cover"
              placeholderClassName="h-24 w-16 shrink-0 [&_svg]:h-8 [&_svg]:w-8"
            />
            <div className="min-w-0">
              <p className="truncate text-xl font-semibold">{top.label}</p>
              <p className="text-sm text-muted-foreground">
                {top.count} {top.count === 1 ? "entry" : "entries"}
              </p>
              {top.mean_score !== null && (
                <span
                  className={cn(
                    "mt-1 inline-block",
                    scoreChipShape,
                    meanScoreChipClass(top.mean_score),
                  )}
                >
                  {top.mean_score.toFixed(1)}
                </span>
              )}
            </div>
          </div>
        )}

        {superlatives.length > 0 && (
          // One tile per row below `sm`: three tiles squeezed into 390px
          // truncated both the label ("2000s" to "2...") and wrapped the title
          // mid-word — a phone gets the room a tile actually needs instead.
          <div className="flex min-w-[15rem] flex-[3] flex-col gap-3 sm:flex-row">
            {superlatives.map((superlative) => (
              <div
                key={superlative.kind}
                className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-surface-raised px-4 py-3 sm:flex-1"
              >
                <CoverImage
                  src={superlative.row.covers[0]}
                  alt=""
                  className="h-12 w-9 shrink-0 object-cover"
                  placeholderClassName="h-12 w-9 shrink-0 [&_svg]:h-5 [&_svg]:w-5"
                />
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">
                    {titles[superlative.kind]}
                  </p>
                  <p className="truncate text-sm font-medium">
                    {superlative.row.label}
                  </p>
                  {stat(superlative)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {superlatives.length > 0 && ratedEntries > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          {ratedEntries} of your {totalEntries} are rated.
        </p>
      )}
    </div>
  );
}
