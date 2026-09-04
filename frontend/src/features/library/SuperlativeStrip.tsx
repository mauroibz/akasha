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
 * Three answers about the leading key's ranking, above the fold (Sprint 067,
 * proposal §2.7): most collected, highest rated, and steadiest. Fewer than three
 * when the library cannot honestly support them (`computeSuperlatives`), and
 * nothing at all for a library with no ranking yet.
 */
export function SuperlativeStrip({
  superlatives,
  totalEntries,
  ratedEntries,
}: {
  superlatives: Superlative[];
  totalEntries: number;
  ratedEntries: number;
}) {
  if (superlatives.length === 0) return null;

  return (
    <div className="mt-6 flex flex-wrap gap-3">
      {superlatives.map((superlative) => (
        <div
          key={superlative.kind}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3"
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
      {ratedEntries > 0 && (
        <p className="w-full text-xs text-muted-foreground">
          {ratedEntries} of your {totalEntries} are rated.
        </p>
      )}
    </div>
  );
}
