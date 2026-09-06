import type { ScoreDistribution } from "@/api/library";
import { Panel } from "@/components/Panel";
import { scoreBand, scoreFillClass } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * The score distribution band (Sprint 073 deliverable 4, proposal §3.2.4).
 *
 * Every other screen paints the score in the ramp; this is the one screen that
 * never drew it as anything but a bare chip beside a count (finding 11). Ten
 * bars, one per score, each in the ramp band its own score belongs to — height
 * carries the count, so the shape of a reader's own rating habit (a bell around
 * 7-8, a cliff at 10, whatever it is) is visible rather than merely knowable.
 *
 * The unrated tail is stated in words rather than drawn as an eleventh bar: it is
 * not a score, and a bar at zero-to-ten's scale would either dwarf the real ones
 * or vanish next to them depending on the library.
 */
export function ScoreDistributionCard({
  distribution,
}: {
  distribution: ScoreDistribution;
}) {
  const max = Math.max(...distribution.counts, 1);

  return (
    <Panel
      data-insight-card=""
      heading="How you rate"
      stat={`${distribution.rated_count} rated`}
      bodyClassName=""
    >
      <div
        role="img"
        aria-label={`Score distribution: ${distribution.counts
          .map((count, index) => `${index + 1} scored by ${count}`)
          .join(", ")}`}
        className="flex h-24 items-end gap-1.5 px-4"
      >
        {distribution.counts.map((count, index) => {
          const score = index + 1;
          const height = count === 0 ? 0 : Math.max((count / max) * 100, 6);
          return (
            <div
              key={score}
              className="flex h-full flex-1 flex-col items-center justify-end gap-1"
            >
              <div
                aria-hidden="true"
                data-score-bar={score}
                data-count={count}
                style={{ height: `${height}%` }}
                className={cn(
                  "w-full min-h-[2px] rounded-t-sm",
                  count > 0 ? scoreFillClass[scoreBand(score)] : "bg-muted",
                )}
              />
              <span className="text-[10px] tabular-nums text-muted-foreground">
                {score}
              </span>
            </div>
          );
        })}
      </div>
      <p className="px-4 pb-4 pt-2 text-xs text-muted-foreground">
        {distribution.unrated_count}{" "}
        {distribution.unrated_count === 1 ? "entry is" : "entries are"} unrated.
      </p>
    </Panel>
  );
}
