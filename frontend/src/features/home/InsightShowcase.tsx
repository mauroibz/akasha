import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getInsights, type Insight, type ItemType } from "@/api/library";
import { rankedSentence, ratingSentence } from "@/features/insights/prose";
import { Prose } from "@/features/insights/sections";
import { countLabel } from "@/features/library/labels";
import { useScoreDistribution } from "@/features/library/useScoreDistribution";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

import { HomeModule } from "./HomeModule";
import { parseInsightKey } from "./layout";

const sentence = "font-display text-lg leading-snug";

function Scores({ type }: { type: string }) {
  const distribution = useScoreDistribution({ type });
  const counts = distribution.data?.counts;
  if (!counts) return null;
  const said = ratingSentence(counts);
  if (!said)
    return (
      <p className="text-sm text-muted-foreground">
        Nothing scored yet. It fills in with your first score.
      </p>
    );
  const most = Math.max(...counts, 1);
  return (
    <>
      <Prose segments={said} className={sentence} />
      {/* One bar per score, 1 to 10, to scale: the Journal's distribution at the
          size of a card. Decorative beside the sentence, which says the same. */}
      <div aria-hidden="true" className="mt-3 flex h-12 items-end gap-1">
        {counts.map((count, index) => (
          <span
            key={index}
            className={cn(
              "flex-1 rounded-t-sm",
              count ? "bg-primary" : "bg-muted",
            )}
            style={{ height: `${Math.max(6, (count / most) * 100)}%` }}
          />
        ))}
      </div>
    </>
  );
}

function Ranked({
  type,
  section,
  types,
}: {
  type: string;
  section: string;
  types: ItemType[] | undefined;
}) {
  const insight = useQuery<Insight>({
    // The Journal asks the same question at its own depth; this is the top of it.
    queryKey: ["insights-top", type, section],
    queryFn: () =>
      getInsights({ type, key: section, metric: "count", limit: 3 }),
    staleTime: 60_000,
  });
  const rows = insight.data?.rows;
  if (!rows) return null;
  if (rows.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        Nothing to count here yet.
      </p>
    );
  const noun = (count: number) => countLabel(count, type, types);
  return (
    <>
      <Prose
        segments={rankedSentence(rows[0], "count", noun)}
        className={sentence}
      />
      <ol className="mt-3 space-y-1 text-sm">
        {rows.map((row) => (
          <li key={row.key} className="flex items-center gap-2">
            <Link
              to={`/?type=${encodeURIComponent(type)}&key=${encodeURIComponent(
                section,
              )}&value=${encodeURIComponent(row.key)}&label=${encodeURIComponent(row.label)}`}
              className="min-w-0 flex-1 truncate font-medium underline-offset-4 hover:underline focus-ring"
            >
              {row.label}
            </Link>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {row.count}
            </span>
            {row.mean_score !== null && (
              <span
                className={cn(
                  scoreChipShape,
                  scoreChipClass(Math.round(row.mean_score)),
                )}
              >
                {row.mean_score.toFixed(1)}
              </span>
            )}
          </li>
        ))}
      </ol>
    </>
  );
}

/**
 * A number from the Journal as a showcase (Sprint 142, DEC-193): one insight
 * section at the size of a card, opening with the sentence the Journal writes for
 * it. `scores` is how a medium is rated; any other section is one of the medium's
 * rankings, its first three rows. It asks the insights endpoints itself, which read
 * stored data only, so a number the person never placed costs nothing.
 */
export function InsightShowcase({
  moduleKey,
  label,
  types,
}: {
  moduleKey: string;
  label: string;
  types: ItemType[] | undefined;
}) {
  const parsed = parseInsightKey(moduleKey);
  if (!parsed) return null;
  return (
    <HomeModule
      title={label}
      aside={
        <Link
          to="/insights"
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          Insights →
        </Link>
      }
    >
      {parsed.section === "scores" ? (
        <Scores type={parsed.type} />
      ) : (
        <Ranked type={parsed.type} section={parsed.section} types={types} />
      )}
    </HomeModule>
  );
}
