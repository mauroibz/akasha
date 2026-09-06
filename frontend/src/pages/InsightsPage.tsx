import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { DomainStrip } from "@/components/DomainStrip";
import { SegmentedControl } from "@/components/SegmentedControl";
import { Input } from "@/components/ui/input";
import {
  domainsFrom,
  formatLabels,
  insightFetchKeys,
  insightKeyOptions,
  statusLabelFor,
} from "@/features/library/labels";
import { ChronologyCard } from "@/features/library/ChronologyCard";
import { InsightsCard } from "@/features/library/InsightsCard";
import { LongTailCard } from "@/features/library/LongTailCard";
import { ScoreDistributionCard } from "@/features/library/ScoreDistributionCard";
import {
  insightGridSpan,
  orderKeys,
  resolveAnsweredKeys,
  type InsightSort,
} from "@/features/library/insights";
import {
  hasRememberedFilters,
  readLibraryFiltersPreference,
  type RememberedLibraryFilters,
} from "@/features/library/library";
import { useInsights } from "@/features/library/useInsights";
import { useScoreDistribution } from "@/features/library/useScoreDistribution";
import { getShelves } from "@/api/shelves";
import type { ItemType, InsightRow } from "@/api/library";
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
  // Off by default (proposal §3): most of a library view mode's value at none
  // of its cost, without giving the library page a fourth responsibility.
  // Read once, the way the remembered domain is: the library page keeps it
  // current in `localStorage` on every filter change it makes.
  const [withinFilters, setWithinFilters] = useState(false);
  const [remembered] = useState<RememberedLibraryFilters>(
    readLibraryFiltersPreference,
  );
  const shelfQuery = useQuery({ queryKey: ["shelves"], queryFn: getShelves });

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

  const activeFilters = withinFilters ? remembered : undefined;
  // A grain group (Decade+Year) fetches both of its keys; `resolveAnsweredKeys`
  // is what turns the flat response array back into one answered entry per
  // *option* (Sprint 073 deliverable 2), not one per request.
  const fetchKeys = useMemo(() => insightFetchKeys(keyOptions), [keyOptions]);
  const rankings = useInsights({
    type,
    keys: fetchKeys,
    includeSuppressed,
    statuses: activeFilters?.statuses,
    shelves: activeFilters?.shelves,
    formats: activeFilters?.formats,
    q: activeFilters?.query,
  });
  const insightByKey = new Map(
    fetchKeys.map((key, index) => [key, rankings[index]?.data]),
  );
  const distribution = useScoreDistribution({
    type,
    statuses: activeFilters?.statuses,
    shelves: activeFilters?.shelves,
    formats: activeFilters?.formats,
    q: activeFilters?.query,
  });

  // Which keys are worth a card, and in what order, is a judgement about this
  // library rather than the order a domain happens to declare its fields
  // (DEC-132). The rest are stated in a line rather than hidden.
  const answered = resolveAnsweredKeys(keyOptions, insightByKey);
  const { carded, quiet } = orderKeys(answered, (entry) => entry.insight.rows);

  const pending = rankings.some((query) => query.isPending);
  const failed =
    rankings.length > 0 && rankings.every((query) => query.isError);

  // Every card's link into the filtered library — `key` is explicit rather than
  // read off `option.name` so a grain card (Sprint 073) can link either of its
  // two grains from the one function.
  const linkTo = (key: string, row: Pick<InsightRow, "key" | "label">) =>
    `/?type=${encodeURIComponent(type)}&key=${encodeURIComponent(
      key,
    )}&value=${encodeURIComponent(row.key)}&label=${encodeURIComponent(
      row.label,
    )}`;

  const [heroEntry, ...restEntries] = carded;

  const renderRankedCard = (
    entry: (typeof carded)[number],
    cardOptions: { hero?: boolean } = {},
  ) => {
    const { option, insight, grainInsight } = entry;
    if (option.grain) {
      return (
        <ChronologyCard
          title={option.label}
          type={type}
          decadeKey={option.name}
          yearKey={option.grain.name}
          yearLabel={option.grain.label}
          decadeInsight={insight}
          yearInsight={grainInsight}
          sort={sort}
          minRated={minRated}
          showSuppressed={includeSuppressed}
          onToggleSuppressed={() => setIncludeSuppressed((shown) => !shown)}
          hero={cardOptions.hero}
          hrefFor={linkTo}
        />
      );
    }
    return (
      <InsightsCard
        title={option.label}
        type={type}
        insightKey={option.name}
        insight={insight}
        sort={sort}
        minRated={minRated}
        showSuppressed={includeSuppressed}
        onToggleSuppressed={() => setIncludeSuppressed((shown) => !shown)}
        hero={cardOptions.hero}
        // `label` is display only, so the library can name the filter rather
        // than echo the normalized value that groups it.
        hrefFor={(row) => linkTo(option.name, row)}
      />
    );
  };

  return (
    <main className="mx-auto min-h-screen max-w-[1600px] px-5 py-8">
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
          className="flex min-w-0 max-w-full flex-wrap items-center gap-3"
        >
          {domains.length > 1 && (
            <DomainStrip domains={domains} value={type} onChange={setType} />
          )}

          {/* A sort order, not a choice of which numbers arrive: every row carries
              both under either one. */}
          <SegmentedControl
            ariaLabel="Sort by"
            value={sort}
            onChange={setSort}
            options={[
              { value: "count", label: "Most collected" },
              { value: "score", label: "Best rated" },
            ]}
          />
        </div>
      </div>

      <ScoreLegend />

      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
        <label className="flex min-h-11 items-center gap-2 text-muted-foreground">
          <input
            type="checkbox"
            checked={withinFilters}
            onChange={(event) => setWithinFilters(event.target.checked)}
            className="h-4 w-4 rounded border-border"
          />
          Within my current filters
        </label>
        {withinFilters && (
          <span className="text-muted-foreground">
            {hasRememberedFilters(remembered)
              ? `Ranking only entries matching ${describeRememberedFilters(
                  remembered,
                  type,
                  itemTypes.data,
                  shelfQuery.data,
                )}.`
              : "Your library has no filters set right now."}
          </span>
        )}
      </div>

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

      {(carded.length > 0 || quiet.length > 0 || distribution.data) && (
        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-12">
          {/* The hero (deliverable 1) always spans the grid, so the leading
              key never competes for width with the cards its own lead earned
              it (AC6). Its superlatives live inside it now (AC3) — this is
              the only card the page draws them on. */}
          {heroEntry && (
            <div className="xl:col-span-12">
              {renderRankedCard(heroEntry, { hero: true })}
            </div>
          )}

          {/* One new number (deliverable 4), domain-wide rather than per key,
              so it sits with the hero rather than competing with a ranking
              for a rank tier it does not have. */}
          {distribution.data && (
            <div className="xl:col-span-12">
              <ScoreDistributionCard distribution={distribution.data} />
            </div>
          )}

          {/* 8/4, then 4/4/4, by `orderKeys`' own rank (deliverable 5) — a
              fifteen-value ranking is not drawn the same size as a
              three-value one, and the pattern repeats past five cards
              because the proposal is silent past five. */}
          {restEntries.map((entry, index) => (
            <div
              key={entry.option.name}
              className={
                insightGridSpan(index) === 8 ? "xl:col-span-8" : "xl:col-span-4"
              }
            >
              {renderRankedCard(entry)}
            </div>
          ))}

          {/* The long tail, as cards instead of a grey footnote (deliverable
              6, finding 12) — each value opens the library filtered to it. */}
          {quiet.map(({ option, insight }) => (
            <div key={option.name} className="xl:col-span-4">
              <LongTailCard
                title={option.label}
                insight={insight}
                hrefFor={(row) => linkTo(option.name, row)}
              />
            </div>
          ))}
        </div>
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

/**
 * What "within my current filters" actually means, in words (Sprint 067
 * deliverable 6) — drawn instead of left for the reader to infer from a
 * narrower ranking they cannot otherwise account for.
 */
function describeRememberedFilters(
  filters: RememberedLibraryFilters,
  type: string,
  types: ItemType[] | undefined,
  shelves: Array<{ slug: string; name: string }> | undefined,
): string {
  const parts: string[] = [];
  if (filters.statuses.length > 0) {
    parts.push(
      filters.statuses
        .map((status) => statusLabelFor(type, types, status))
        .join("/"),
    );
  }
  if (filters.shelves.length > 0) {
    const names = new Map(
      (shelves ?? []).map((shelf) => [shelf.slug, shelf.name]),
    );
    parts.push(
      filters.shelves.map((slug) => names.get(slug) ?? slug).join("/"),
    );
  }
  if (filters.formats.length > 0) {
    const labels = formatLabels(types);
    parts.push(
      filters.formats.map((value) => labels[value] ?? value).join("/"),
    );
  }
  if (filters.query.trim()) parts.push(`"${filters.query.trim()}"`);
  return parts.join(" · ");
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
