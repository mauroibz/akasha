import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { domainsFrom, insightKeyOptions } from "@/features/library/labels";
import { InsightsCard } from "@/features/library/InsightsCard";
import {
  orderKeys,
  quietSummary,
  type InsightSort,
} from "@/features/library/insights";
import { useInsights } from "@/features/library/useInsights";
import type { Insight } from "@/api/library";
import { useItemTypes } from "@/features/library/useItemTypes";

/**
 * Ask the library a question it already has the answer to — which authors you rate
 * highest, which bands you own most of — from the fields items already declare
 * (Sprint 065). Never crosses domains: DEC-052 and DEC-077 twice declined to create
 * the cross-domain creator identity that would need, and this feature exists to keep
 * it that way. A ranking row links into the filtered library, not to a new entity
 * screen of its own.
 *
 * Redrawn in Sprint 066 (DEC-132). It was a query builder — four controls above one
 * table, one question per visit, and the only interaction navigated away. It answers
 * on arrival now: one card per key, both numbers on every row, and the accent
 * spent on encoding a quantity rather than on colouring every label alike.
 */
export function InsightsPage() {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const itemTypes = useItemTypes();
  const domains = useMemo(() => domainsFrom(itemTypes.data), [itemTypes.data]);

  const [type, setType] = useState("");
  const [sort, setSort] = useState<InsightSort>("count");
  const [minRated, setMinRated] = useState(2);
  const [includeSuppressed, setIncludeSuppressed] = useState(false);

  // The registry loads after this component mounts, so the first domain is chosen
  // once it arrives rather than assumed up front.
  useEffect(() => {
    if (type || domains.length === 0) return;
    setType(domains[0].id);
  }, [domains, type]);

  const selectedDomain = domains.find((domain) => domain.id === type);
  const keyOptions = useMemo(
    () => (selectedDomain ? insightKeyOptions(selectedDomain.fields) : []),
    [selectedDomain],
  );

  const rankings = useInsights({
    type,
    keys: keyOptions.map((option) => option.name),
    includeSuppressed,
  });

  // Which keys are worth a card, and in what order, is a judgement about this
  // library rather than the order a domain happens to declare its fields
  // (DEC-132). The rest are stated in a line rather than hidden. Not memoized:
  // it is a sort of at most a handful of keys, and a dependency array over an
  // array rebuilt every render would only pretend otherwise.
  type Answered = { option: (typeof keyOptions)[number]; insight: Insight };
  const answered = keyOptions
    .map((option, index) => ({ option, insight: rankings[index]?.data }))
    .filter((entry): entry is Answered => Boolean(entry.insight));
  const { carded, quiet } = orderKeys(answered, (entry) => entry.insight.rows);

  const pending = rankings.some((query) => query.isPending);
  const failed =
    rankings.length > 0 && rankings.every((query) => query.isError);

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="text-4xl font-semibold focus:outline-none"
          >
            Insights
          </h1>
          <p className="mt-2 text-muted-foreground">
            What your library already declares, ranked — one domain at a time.
          </p>
        </div>

        {/* A group, not a region: the landmark belongs to the rankings, and a
            toolbar of two toggles is not a significant content area. */}
        <div
          role="group"
          aria-label="Ranking controls"
          className="flex flex-wrap items-center gap-3"
        >
          {domains.length > 1 && (
            <div
              role="radiogroup"
              aria-label="Choose a domain"
              className="inline-flex shrink-0 rounded-full bg-surface p-1"
            >
              {domains.map((choice) => (
                <button
                  key={choice.id}
                  type="button"
                  role="radio"
                  aria-checked={type === choice.id}
                  className={`min-h-11 rounded-full px-5 py-2 text-sm font-medium transition-colors ${
                    type === choice.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  } focus-ring`}
                  onClick={() => setType(choice.id)}
                >
                  {choice.label}
                </button>
              ))}
            </div>
          )}

          {/* A sort order, not a choice of which numbers arrive: every row carries
              both under either one. */}
          <div
            className="flex rounded-full bg-surface p-1"
            role="group"
            aria-label="Sort by"
          >
            <Button
              variant="ghost"
              size="sm"
              aria-pressed={sort === "count"}
              className="rounded-full aria-pressed:bg-surface-raised"
              onClick={() => setSort("count")}
            >
              Most collected
            </Button>
            <Button
              variant="ghost"
              size="sm"
              aria-pressed={sort === "score"}
              className="rounded-full aria-pressed:bg-surface-raised"
              onClick={() => setSort("score")}
            >
              Best rated
            </Button>
          </div>
        </div>
      </div>

      <ScoreLegend />

      {pending && carded.length === 0 && (
        <p role="status" className="mt-8 text-muted-foreground">
          Ranking…
        </p>
      )}
      {failed && (
        <p role="alert" className="mt-8 text-destructive">
          Insights could not be loaded
        </p>
      )}

      {carded.length > 0 && (
        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          {carded.map(({ option, insight }) => (
            <InsightsCard
              key={option.name}
              title={option.label}
              type={type}
              insightKey={option.name}
              insight={insight}
              sort={sort}
              minRated={minRated}
              showSuppressed={includeSuppressed}
              onToggleSuppressed={() => setIncludeSuppressed((shown) => !shown)}
              // `label` is display only, so the library can name the filter
              // rather than echo the normalized value that groups it.
              hrefFor={(row) =>
                `/?type=${encodeURIComponent(type)}&key=${encodeURIComponent(
                  option.name,
                )}&value=${encodeURIComponent(
                  row.key,
                )}&label=${encodeURIComponent(row.label)}`
              }
            />
          ))}
        </div>
      )}

      {quiet.length > 0 && (
        <section
          aria-labelledby="quiet-keys"
          className="mt-4 rounded-xl border border-border px-4 py-3"
        >
          <h2
            id="quiet-keys"
            className="text-xs font-semibold text-muted-foreground"
          >
            Nothing much to rank yet
          </h2>
          <ul className="mt-1.5 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
            {quiet.map(({ option, insight }) => (
              <li key={option.name}>
                <span className="text-foreground">{option.label}</span> —{" "}
                {quietSummary(insight.rows)}
              </li>
            ))}
          </ul>
        </section>
      )}

      {sort === "score" && carded.length > 0 && (
        <label className="mt-5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          A value is placed in the score order from
          <Input
            type="number"
            min={1}
            aria-label="Ratings needed to place in the score order"
            value={minRated}
            onChange={(event) =>
              setMinRated(Math.max(1, Number(event.target.value) || 1))
            }
            className="h-9 w-16 rounded-full text-center"
          />
          ratings up.
        </label>
      )}
    </main>
  );
}

/** The ramp, explained once, because every card leans on it. */
function ScoreLegend() {
  const bands: Array<[string, string]> = [
    ["bg-score-low", "1–3"],
    ["bg-score-mid", "4–6"],
    ["bg-score-high", "7–8"],
    ["bg-score-top", "9–10"],
  ];
  return (
    <p className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
      <span>
        Bar length is how many you hold; the chip is how you rate them.
      </span>
      <span className="flex items-center gap-2">
        {bands.map(([background, range]) => (
          <span key={range} className="flex items-center gap-1">
            <span
              aria-hidden="true"
              className={`inline-block h-2 w-3.5 rounded-sm ${background}`}
            />
            {range}
          </span>
        ))}
      </span>
    </p>
  );
}
