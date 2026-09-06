import { useId } from "react";
import { Link } from "react-router-dom";

import type { Insight, InsightRow } from "@/api/library";
import { Panel } from "@/components/Panel";
import { quietSummary } from "@/features/library/insights";

/**
 * A key with nothing worth ranking, as a card instead of a footnote line
 * (Sprint 073 deliverable 6, finding 12) — "16 subjects appear once" is a
 * clickable tag row into the filtered library now, not a grey sentence nobody
 * reads. `orderKeys` already decided this key is not a ranking (`keyLead` found
 * no lead worth drawing bars over); the card states its whole truth in one line
 * and lets every value open the library filtered to it.
 */
export function LongTailCard({
  title,
  insight,
  hrefFor,
}: {
  title: string;
  insight: Insight;
  hrefFor: (row: InsightRow) => string;
}) {
  const headingId = useId();
  return (
    <Panel
      aria-labelledby={headingId}
      data-insight-card=""
      data-long-tail-card=""
      heading={title}
      headingId={headingId}
      stat={quietSummary(insight.rows)}
    >
      <div className="flex flex-wrap gap-2">
        {insight.rows.map((row) => (
          <Link
            key={row.key}
            to={hrefFor(row)}
            className="inline-flex min-h-11 items-center rounded-full border border-border px-3 text-xs font-medium hover:border-muted-foreground hover:bg-surface-raised focus-ring"
          >
            {row.label}{" "}
            <span className="ml-1 text-muted-foreground">{row.count}</span>
          </Link>
        ))}
      </div>
    </Panel>
  );
}
