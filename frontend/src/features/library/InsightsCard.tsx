import { useId, useState } from "react";

import type { Insight, InsightRow } from "@/api/library";
import { Panel } from "@/components/Panel";
import { InsightsRanking } from "@/features/library/InsightsRanking";
import {
  computeSuperlatives,
  orderRows,
  type InsightSort,
} from "@/features/library/insights";
import { insightDepth } from "@/features/library/useInsights";
import { HeroSummary } from "@/features/library/HeroSummary";

/** How many rows a card shows before it has to be asked for the rest. */
const preview = 6;

/**
 * One key's ranking, as a card (Sprint 066).
 *
 * Sprint 065 put every key behind one popover, so seeing authors and then subjects
 * was two selections and two refetches, and the alternatives were invisible while
 * choosing. A card each means the page answers on arrival.
 *
 * The title is the label the *domain* declares — `Artists` for albums, `Authors`
 * for books. The shipped table printed the raw field name, lowercased, for every
 * domain alike.
 *
 * `hero` (Sprint 073 deliverable 1) promotes this into the leading key's hero
 * panel: its own top row (by whichever order is active) drawn large above the
 * ordinary list, and the three superlatives folded in beneath it — the fix for
 * finding 9, where a page-level strip repeated the very card it sat above. Their
 * only home is here now (AC3).
 */
export function InsightsCard({
  title,
  type,
  insightKey,
  insight,
  sort,
  minRated,
  showSuppressed,
  onToggleSuppressed,
  hrefFor,
  hero = false,
}: {
  title: string;
  type: string;
  insightKey: string;
  insight: Insight;
  sort: InsightSort;
  minRated: number;
  showSuppressed: boolean;
  onToggleSuppressed: () => void;
  hrefFor: (row: InsightRow) => string;
  /** Promote this card into the page's hero (deliverable 1). */
  hero?: boolean;
}) {
  const [showAll, setShowAll] = useState(false);
  const headingId = useId();

  const { placed, unplaced } = orderRows(insight.rows, sort, minRated);
  const shown = showAll ? placed : placed.slice(0, preview);
  const hidden = placed.length - shown.length;
  const deep = insight.rows.filter((row) => row.count > 1).length;
  const top = hero ? placed[0] : undefined;
  const superlatives = hero ? computeSuperlatives(insight.rows, minRated) : [];

  return (
    <Panel
      aria-labelledby={headingId}
      data-insight-card=""
      data-insight-hero={hero ? "" : undefined}
      className="flex flex-col"
      bodyClassName=""
      heading={title}
      headingId={headingId}
      stat={
        <>
          {insight.rows.length} in all · {deep} held more than once
        </>
      }
    >
      {hero && (
        <HeroSummary
          top={top}
          superlatives={superlatives}
          totalEntries={insight.total_entries}
          ratedEntries={insight.rated_entries}
        />
      )}

      {placed.length === 0 && unplaced.length === 0 && (
        <p className="px-4 pb-4 text-sm text-muted-foreground">
          Nothing to rank here yet.
        </p>
      )}

      {placed.length === 0 && unplaced.length > 0 && (
        <p className="px-4 pb-2 text-sm text-muted-foreground">
          Nothing is rated enough to sort by score yet — lower the threshold, or
          sort by how many you hold.
        </p>
      )}

      <div className="px-2 pb-1">
        <InsightsRanking
          rows={shown}
          unplaced={unplaced}
          type={type}
          insightKey={insightKey}
          hrefFor={hrefFor}
        />
      </div>

      {hidden > 0 && (
        <button
          type="button"
          className="mx-2 mb-2 min-h-11 rounded-md px-3 text-left text-xs text-muted-foreground hover:bg-surface-raised hover:text-foreground focus-ring"
          onClick={() => setShowAll(true)}
        >
          Show {hidden} more
        </button>
      )}

      <CardNotes
        insight={insight}
        showSuppressed={showSuppressed}
        onToggleSuppressed={onToggleSuppressed}
      />
    </Panel>
  );
}

/**
 * What the ranking left out, in the card that left it out.
 *
 * Sprint 065 put these under the whole page as grey paragraphs — the right
 * information in the least likely place to be read, and detached from the ranking
 * they describe once there is more than one.
 */
export function CardNotes({
  insight,
  showSuppressed,
  onToggleSuppressed,
}: {
  insight: Insight;
  showSuppressed: boolean;
  onToggleSuppressed: () => void;
}) {
  const suppressed = insight.suppressed;
  const notes: React.ReactNode[] = [];

  if (suppressed.length > 0) {
    notes.push(
      <button
        key="suppressed"
        type="button"
        className="rounded-full border border-dashed border-border px-2.5 py-1 hover:border-muted-foreground hover:text-foreground focus-ring"
        onClick={onToggleSuppressed}
      >
        {suppressed.map((row) => row.label).join(", ")}{" "}
        {showSuppressed ? "shown — hide" : "hidden — show"}
      </button>,
    );
  }
  if (insight.null_count > 0) {
    notes.push(
      <span key="nulls">
        {insight.null_count}{" "}
        {insight.null_count === 1 ? "entry has" : "entries have"} no year
      </span>,
    );
  }
  if (insight.next_cursor) {
    notes.push(
      <span key="depth">ranked over the {insightDepth} most held</span>,
    );
  }

  if (notes.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border/60 px-4 py-2.5 text-xs text-muted-foreground">
      {notes}
    </div>
  );
}
