import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import {
  getInsightSummary,
  type InsightRow,
  type ItemType,
} from "@/api/library";
import { queryKeys } from "@/api/keys";
import { getShelves } from "@/api/shelves";
import { Loading } from "@/components/ui/skeleton";
import { leadSentence, readsAsShares } from "@/features/insights/prose";
import {
  ChronologySection,
  Prose,
  RankedSection,
  RatingSection,
  RestSection,
  SharesSection,
  TermsSection,
} from "@/features/insights/sections";
import {
  orderKeys,
  resolveAnsweredKeys,
  type AnsweredInsightKey,
} from "@/features/library/insights";
import {
  countLabel,
  domainsFrom,
  formatLabels,
  insightFetchKeys,
  insightKeyOptions,
  statusLabelFor,
} from "@/features/library/labels";
import {
  hasRememberedFilters,
  readLibraryFiltersPreference,
  type RememberedLibraryFilters,
} from "@/features/library/library";
import { useInsights } from "@/features/library/useInsights";
import { useItemTypes } from "@/features/library/useItemTypes";
import { useScoreDistribution } from "@/features/library/useScoreDistribution";
import { cn } from "@/lib/utils";

/**
 * Ask the library a question it already has the answer to, from the fields items
 * already declare (Sprint 065). Never crosses domains (DEC-052, DEC-077).
 *
 * Read back as prose since Sprint 102 (DEC-169). The owner on the card grid that
 * Sprints 066–073 built: "a bunch of boxes with floating text, charts too large".
 * The page now opens on one sentence carrying the figures that matter, then
 * numbered sections divided by rules: a sentence each, and a chart no bigger
 * than its data. Which key earns which form is still a judgement about this
 * library (`orderKeys`), never a domain name.
 */
export function InsightsPage() {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const itemTypes = useItemTypes();
  const domains = useMemo(() => domainsFrom(itemTypes.data), [itemTypes.data]);
  const [type, setType] = useState("");
  const [includeSuppressed, setIncludeSuppressed] = useState(false);
  // Off by default: the library page keeps the remembered filters current in
  // `localStorage`, and this reads them once (Sprint 067 deliverable 5).
  const [withinFilters, setWithinFilters] = useState(false);
  const [remembered] = useState<RememberedLibraryFilters>(
    readLibraryFiltersPreference,
  );
  const shelfQuery = useQuery({
    queryKey: queryKeys.shelves,
    queryFn: getShelves,
  });

  useEffect(() => {
    if (type || domains.length === 0) return;
    setType(domains[0].id);
  }, [domains, type]);

  const selectedDomain = domains.find((domain) => domain.id === type);
  const keyOptions = useMemo(
    () => (selectedDomain ? insightKeyOptions(selectedDomain.fields) : []),
    [selectedDomain],
  );
  const filters = withinFilters ? remembered : undefined;
  const filterParams = {
    statuses: filters?.statuses,
    shelves: filters?.shelves,
    formats: filters?.formats,
    q: filters?.query,
  };
  const fetchKeys = useMemo(() => insightFetchKeys(keyOptions), [keyOptions]);
  const rankings = useInsights({
    type,
    keys: fetchKeys,
    includeSuppressed,
    ...filterParams,
  });
  const insightByKey = new Map(
    fetchKeys.map((key, index) => [key, rankings[index]?.data]),
  );
  const distribution = useScoreDistribution({ type, ...filterParams });
  const summary = useQuery({
    queryKey: ["insights-summary", type, filterParams],
    queryFn: () => getInsightSummary({ type, ...filterParams }),
    enabled: Boolean(type),
  });

  const noun = (count: number) => countLabel(count, type, itemTypes.data);
  const linkTo = (key: string, row: Pick<InsightRow, "key" | "label">) =>
    `/?type=${encodeURIComponent(type)}&key=${encodeURIComponent(
      key,
    )}&value=${encodeURIComponent(row.key)}&label=${encodeURIComponent(row.label)}`;

  const answered = resolveAnsweredKeys(keyOptions, insightByKey);
  const chronology = answered.find((entry) => entry.option.grain);
  const { carded, quiet } = orderKeys(
    answered.filter((entry) => !entry.option.grain),
    (entry) => entry.insight.rows,
  );
  // The ranked list goes to the first key, in the domain's own declared order,
  // that leads by the `keyLead` measure: a domain declares its creators first,
  // and "who you return to" is the question this list answers best. A small
  // library may have no leading key; then the one with the most values takes
  // it, so the page still has a face.
  const unpinned = answered.filter((entry) => !entry.option.grain);
  const ranked: AnsweredInsightKey | undefined =
    unpinned.find((entry) => carded.includes(entry)) ??
    [...quiet]
      .filter((entry) => entry.insight.rows.length >= 3)
      .sort((a, b) => b.insight.rows.length - a.insight.rows.length)[0];
  const others = [...carded, ...quiet].filter((entry) => entry !== ranked);
  const shares = others.filter((entry) => readsAsShares(entry.insight.rows));
  const terms = carded.filter(
    (entry) => entry !== ranked && !readsAsShares(entry.insight.rows),
  );
  const rest = quiet.filter(
    (entry) => entry !== ranked && !readsAsShares(entry.insight.rows),
  );

  const pending =
    rankings.some((query) => query.isPending) || summary.isPending;
  const failed =
    summary.isError ||
    (rankings.length > 0 && rankings.every((query) => query.isError));
  const leader = ranked
    ? [...ranked.insight.rows].sort((a, b) => b.count - a.count)[0]
    : undefined;

  const sections: Array<(number: number) => ReactNode> = [];
  if (distribution.data) {
    const data = distribution.data;
    sections.push((number) => (
      <RatingSection
        key="rating"
        number={number}
        counts={data.counts}
        unrated={data.unrated_count}
      />
    ));
  }
  if (ranked) {
    sections.push((number) => (
      <RankedSection
        key={`ranked-${type}-${ranked.option.name}`}
        number={number}
        title={ranked.option.label}
        type={type}
        insightKey={ranked.option.name}
        rows={ranked.insight.rows}
        suppressed={ranked.insight.suppressed}
        showSuppressed={includeSuppressed}
        onToggleSuppressed={() => setIncludeSuppressed((shown) => !shown)}
        noun={noun}
        hrefFor={(row) => linkTo(ranked.option.name, row)}
      />
    ));
  }
  for (const entry of terms) {
    sections.push((number) => (
      <TermsSection
        key={`terms-${entry.option.name}`}
        number={number}
        title={entry.option.label}
        rows={entry.insight.rows}
        hrefFor={(row) => linkTo(entry.option.name, row)}
      />
    ));
  }
  if (chronology && chronology.insight.rows.length > 0) {
    sections.push((number) => (
      <ChronologySection
        key={`chronology-${type}`}
        number={number}
        title={chronology.option.label}
        coarse={{ key: chronology.option.name, rows: chronology.insight.rows }}
        fine={
          chronology.option.grain && chronology.grainInsight
            ? {
                key: chronology.option.grain.name,
                rows: chronology.grainInsight.rows,
              }
            : undefined
        }
        fineLabel={chronology.option.grain?.label ?? ""}
        earliest={summary.data?.earliest ?? null}
        noun={noun}
        hrefFor={linkTo}
      />
    ));
  }
  for (const entry of shares) {
    sections.push((number) => (
      <SharesSection
        key={`shares-${entry.option.name}`}
        number={number}
        title={entry.option.label}
        rows={entry.insight.rows}
        hrefFor={(row) => linkTo(entry.option.name, row)}
      />
    ));
  }
  if (rest.length > 0) {
    sections.push((number) => (
      <RestSection
        key="rest"
        number={number}
        keys={rest.map((entry) => ({
          name: entry.option.name,
          label: entry.option.label,
          rows: entry.insight.rows,
        }))}
        hrefFor={linkTo}
      />
    ));
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-5 pb-24 pt-8 md:pt-12">
      <h1
        ref={headingRef}
        tabIndex={-1}
        className="font-display text-5xl font-medium tracking-tight focus:outline-none md:text-6xl"
      >
        Insights
      </h1>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-x-6 border-b border-border">
        {domains.length > 1 && (
          <div
            role="radiogroup"
            aria-label="Choose a domain"
            className="-mb-px flex min-w-0 max-w-full gap-6 overflow-x-auto"
          >
            {domains.map((domain) => (
              <button
                key={domain.id}
                type="button"
                role="radio"
                aria-checked={domain.id === type}
                onClick={() => setType(domain.id)}
                className={cn(
                  "min-h-11 shrink-0 border-b-2 px-0.5 text-[15px] font-medium transition-colors focus-ring",
                  domain.id === type
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {domain.plural_label ?? domain.label}
              </button>
            ))}
          </div>
        )}
        <label className="flex min-h-11 items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={withinFilters}
            onChange={(event) => setWithinFilters(event.target.checked)}
            className="h-4 w-4 rounded border-border accent-[hsl(var(--primary-text))]"
          />
          Only what the library is filtered to
        </label>
      </div>
      {withinFilters && (
        <p className="mt-3 text-sm text-muted-foreground">
          {hasRememberedFilters(remembered)
            ? `Reading only entries matching ${describeRememberedFilters(
                remembered,
                type,
                itemTypes.data,
                shelfQuery.data,
              )}.`
            : "Your library has no filters set right now."}
        </p>
      )}

      {failed && (
        <p role="alert" className="mt-10 text-destructive">
          Insights could not be loaded
        </p>
      )}
      {!failed && pending && !summary.data && (
        <Loading label="Reading your library" className="mt-12" />
      )}

      {summary.data && summary.data.held === 0 && (
        <p className="mt-12 max-w-[30ch] font-display text-3xl leading-tight text-muted-foreground">
          Nothing here yet. Insights read what you keep, so add a few and come
          back.
        </p>
      )}

      {summary.data && summary.data.held > 0 && (
        <>
          <Prose
            segments={leadSentence({ summary: summary.data, noun, leader })}
            className="mb-14 mt-12 max-w-[26ch] font-display text-[2rem] leading-[1.18] tracking-[-0.01em] md:text-5xl"
          />
          {sections.map((render, index) => render(index + 1))}
        </>
      )}
    </main>
  );
}

/** What "only what the library is filtered to" means, in words (Sprint 067). */
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
