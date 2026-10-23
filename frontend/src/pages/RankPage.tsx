import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { DomainStrip } from "@/components/DomainStrip";
import { PageHeader } from "@/components/PageHeader";
import { countLabel, domainsFrom } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { useScoreDistribution } from "@/features/library/useScoreDistribution";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * Which score to put in order (Sprint 116, DEC-176): for one library, every score
 * that two or more entries share, the most common marked as Insights marks it.
 */
export function RankPage() {
  const itemTypes = useItemTypes();
  const domains = domainsFrom(itemTypes.data);
  const [chosen, setChosen] = useState<string | null>(null);
  const type = chosen ?? domains[0]?.id ?? "";
  const distribution = useScoreDistribution({ type });
  const counts = distribution.data?.counts ?? [];
  const scores = counts
    .map((count, index) => ({ score: index + 1, count }))
    .filter((row) => row.count >= 2)
    .reverse();

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-5 py-8">
      <PageHeader
        back
        title="Put your scores in order"
        lede="Choose between two at a time. The order sits inside a score and never changes one."
      />
      {domains.length > 1 && (
        <DomainStrip
          domains={domains}
          value={type}
          onChange={setChosen}
          className="mt-6"
        />
      )}
      {scores.length > 0 && (
        <ul aria-label="Scores to put in order" className="mt-6 grid gap-2">
          {scores.map(({ score, count }) => (
            <li key={score}>
              <Link
                to={`/rank/${type}/${score}`}
                className="flex items-center gap-4 rounded-xl border border-border bg-surface p-4 transition-colors hover:bg-accent focus-ring"
              >
                <span
                  className={cn(
                    scoreChipShape,
                    scoreChipClass(score),
                    "text-lg",
                  )}
                >
                  {score}
                </span>
                <span className="flex-1">
                  {countLabel(count, type, itemTypes.data)}
                </span>
                <ArrowRight
                  className="h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {distribution.data && scores.length === 0 && (
        <p className="mt-6 text-muted-foreground">
          No score is shared by two yet, so there is nothing to put in order.
        </p>
      )}
    </main>
  );
}
