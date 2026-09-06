import { useId, useState } from "react";

import type { Insight, InsightRow } from "@/api/library";
import { Panel } from "@/components/Panel";
import { SegmentedControl } from "@/components/SegmentedControl";
import { CardNotes } from "@/features/library/InsightsCard";
import { InsightsRanking } from "@/features/library/InsightsRanking";
import {
  chronologyBuckets,
  computeSuperlatives,
  orderRows,
  type InsightSort,
} from "@/features/library/insights";
import { ChronologyStrip } from "@/features/library/ChronologyStrip";
import { HeroSummary } from "@/features/library/HeroSummary";

type Grain = "decade" | "year";

/** How many rows the Year grain shows before it has to be asked for the rest. */
const preview = 6;

/**
 * Decade and Year, as one card with a grain toggle (Sprint 073 deliverable 2) —
 * they are one fact at two resolutions (finding 8), and the rollup declaration
 * that makes this general rather than a hard-coded pair lives in
 * `labels.ts`'s `InsightKeyOption.grain`.
 *
 * The coarse grain draws as `ChronologyStrip` (deliverable 3: time order, not
 * ranked order). The fine grain — potentially dozens of distinct years — keeps
 * the ordinary ranked bar list every other card uses, since a strip of forty
 * slivers is not more legible than a ranking.
 */
export function ChronologyCard({
  title,
  type,
  decadeKey,
  yearKey,
  yearLabel,
  decadeInsight,
  yearInsight,
  sort,
  minRated,
  showSuppressed,
  onToggleSuppressed,
  hrefFor,
  hero = false,
}: {
  title: string;
  type: string;
  decadeKey: string;
  yearKey: string;
  yearLabel: string;
  decadeInsight: Insight;
  yearInsight: Insight | undefined;
  sort: InsightSort;
  minRated: number;
  showSuppressed: boolean;
  onToggleSuppressed: () => void;
  hrefFor: (key: string, row: Pick<InsightRow, "key" | "label">) => string;
  /** Promote this card into the page's hero (Sprint 073 deliverable 1) — the
   * chronology card earns the lead as often as any other key, so it needs the
   * same promoted top row and superlatives every other hero gets (AC3). */
  hero?: boolean;
}) {
  const [grain, setGrain] = useState<Grain>("decade");
  const [showAll, setShowAll] = useState(false);
  const headingId = useId();
  const active =
    grain === "decade" ? decadeInsight : (yearInsight ?? decadeInsight);
  const deep = decadeInsight.rows.filter((row) => row.count > 1).length;
  const decadeByCount = [...decadeInsight.rows].sort(
    (a, b) => b.count - a.count || a.key.localeCompare(b.key),
  );
  const top = hero ? decadeByCount[0] : undefined;
  const superlatives = hero
    ? computeSuperlatives(decadeInsight.rows, minRated)
    : [];

  const { placed, unplaced } =
    grain === "year" && yearInsight
      ? orderRows(yearInsight.rows, sort, minRated)
      : { placed: [], unplaced: [] };
  const shown = showAll ? placed : placed.slice(0, preview);
  const hidden = placed.length - shown.length;

  return (
    <Panel
      aria-labelledby={headingId}
      data-insight-card=""
      data-chronology-card=""
      data-insight-hero={hero ? "" : undefined}
      className="flex flex-col"
      bodyClassName=""
    >
      <div className="flex items-center justify-between gap-3 px-4 pb-2 pt-4">
        <h2 id={headingId} className="text-sm font-semibold">
          {title}
        </h2>
        <SegmentedControl
          ariaLabel={`${title} grain`}
          value={grain}
          onChange={setGrain}
          className="p-0.5"
          options={[
            { value: "decade", label: "Decade" },
            { value: "year", label: yearLabel },
          ]}
        />
      </div>

      {hero && (
        <HeroSummary
          top={top}
          superlatives={superlatives}
          totalEntries={decadeInsight.total_entries}
          ratedEntries={decadeInsight.rated_entries}
        />
      )}

      {grain === "decade" && (
        <ChronologyStrip
          buckets={chronologyBuckets(decadeInsight.rows)}
          hrefFor={(bucket) =>
            hrefFor(decadeKey, {
              key: String(bucket.decade),
              label: bucket.label,
            })
          }
        />
      )}

      {grain === "year" &&
        (yearInsight ? (
          <>
            {placed.length === 0 && unplaced.length > 0 && (
              <p className="px-4 pb-2 text-sm text-muted-foreground">
                Nothing is rated enough to sort by score yet — lower the
                threshold, or sort by how many you hold.
              </p>
            )}
            <div className="px-2 pb-1">
              <InsightsRanking
                rows={shown}
                unplaced={unplaced}
                type={type}
                insightKey={yearKey}
                hrefFor={(row) => hrefFor(yearKey, row)}
              />
            </div>
          </>
        ) : (
          <p role="status" className="px-4 pb-4 text-sm text-muted-foreground">
            Ranking…
          </p>
        ))}

      {grain === "year" && hidden > 0 && (
        <button
          type="button"
          className="mx-2 mb-2 min-h-11 rounded-md px-3 text-left text-xs text-muted-foreground hover:bg-surface-raised hover:text-foreground focus-ring"
          onClick={() => setShowAll(true)}
        >
          Show {hidden} more
        </button>
      )}

      <p className="px-4 pt-1 text-xs text-muted-foreground">
        {decadeInsight.rows.length} decades in all · {deep} held more than once
      </p>

      <CardNotes
        insight={active}
        showSuppressed={showSuppressed}
        onToggleSuppressed={onToggleSuppressed}
      />
    </Panel>
  );
}
