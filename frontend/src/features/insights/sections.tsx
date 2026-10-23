import { useId, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { InsightRow, InsightSummary } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import {
  chronologySentence,
  modalScore,
  rankedSentence,
  ratingSentence,
  shareSentence,
  termSize,
  termsSentence,
  type Noun,
  type Segment,
} from "@/features/insights/prose";
import { InsightsMembers } from "@/features/library/InsightsMembers";
import {
  chronologyBuckets,
  orderRows,
  type InsightSort,
} from "@/features/library/insights";
import { meanScoreChipClass, scoreBand, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * The redrawn insights page's parts (Sprint 102, DEC-169): numbered sections
 * divided by a rule, each a sentence and a chart no bigger than its data. The
 * old page boxed every key in a card of the same weight; here the sizes are
 * uneven on purpose, and the type carries the hierarchy.
 */

export type HrefFor = (row: Pick<InsightRow, "key" | "label">) => string;

/** A sentence with its figures set apart. */
export function Prose({
  segments,
  className,
}: {
  segments: Segment[];
  className?: string;
}) {
  return (
    <p className={className}>
      {segments.map((segment, index) =>
        segment.em ? (
          <span key={index} className="text-primary">
            {segment.text}
          </span>
        ) : (
          <span key={index}>{segment.text}</span>
        ),
      )}
    </p>
  );
}

export function Section({
  number,
  title,
  aside,
  children,
}: {
  number: number;
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      data-insight-section=""
      className="grid gap-4 border-t border-border py-10 md:grid-cols-[13rem_minmax(0,1fr)] md:gap-10 md:py-12"
    >
      <div>
        <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground tabular-nums">
          {String(number).padStart(2, "0")}
        </div>
        <h2
          id={headingId}
          className="mt-1 font-display text-2xl font-medium leading-tight md:text-3xl"
        >
          {title}
        </h2>
        {aside}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

const sentenceClass =
  "max-w-[40ch] font-display text-xl leading-snug md:text-2xl";

const barFill: Record<ReturnType<typeof scoreBand>, string> = {
  low: "bg-score-low",
  mid: "bg-score-mid",
  high: "bg-score-high",
  top: "bg-score-top",
};

/** How you rate: the usual score drawn huge, the ten scores drawn small. */
export function RatingSection({
  number,
  counts,
  unrated,
  type,
}: {
  number: number;
  counts: number[];
  unrated: number;
  /** The domain, for the way into ordering the most common score (Sprint 116). */
  type?: string;
}) {
  const sentence = ratingSentence(counts);
  const modal = modalScore(counts);
  if (sentence === null || modal === null) return null;
  const max = Math.max(...counts, 1);
  const described = counts
    .map((count, index) => `${index + 1}: ${count}`)
    .join(", ");
  return (
    <Section number={number} title="How you rate">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-6">
        <div
          aria-hidden="true"
          className={cn(
            "font-display text-[7rem] font-medium leading-[0.8] tabular-nums md:text-[9rem]",
            {
              low: "text-score-low",
              mid: "text-score-mid",
              high: "text-score-high",
              top: "text-score-top",
            }[scoreBand(modal)],
          )}
        >
          {modal}
        </div>
        <div className="min-w-0 flex-1">
          <Prose segments={sentence} className={sentenceClass} />
          <div
            role="img"
            aria-label={`How many you gave each score, ${described}.`}
            className="mt-6 flex h-[4.5rem] max-w-md items-end gap-1.5"
          >
            {counts.map((count, index) => (
              <div
                key={index}
                className="flex h-full flex-1 flex-col items-center justify-end gap-1.5"
              >
                <div
                  data-score-bar={index + 1}
                  style={{
                    height: count
                      ? `${Math.max(8, (count / max) * 100)}%`
                      : "2px",
                  }}
                  className={cn(
                    "w-full rounded-sm",
                    count ? barFill[scoreBand(index + 1)] : "bg-border",
                  )}
                />
                <span className="text-[11px] leading-none text-muted-foreground">
                  {index + 1}
                </span>
              </div>
            ))}
          </div>
          {unrated > 0 && (
            <p className="mt-4 text-sm text-muted-foreground">
              {unrated.toLocaleString()} unrated, counted everywhere but here.
            </p>
          )}
          {/* Insights says where most scores land; this is something to do about it
              that never changes a score (Sprint 116, DEC-176). */}
          {type && counts[modal - 1] >= 2 && (
            <p className="mt-2 text-sm">
              <Link
                to={`/rank/${type}/${modal}`}
                className="inline-flex min-h-11 items-center font-medium text-primary-text underline-offset-4 hover:underline focus-ring"
              >
                Put your {modal}s in order
              </Link>
            </p>
          )}
        </div>
      </div>
    </Section>
  );
}

/** What a screen reader is told a ranked row holds. */
function rowLabel(row: InsightRow, noun: Noun): string {
  const held = noun(row.count);
  if (row.mean_score === null) return `${row.label}: ${held}, none rated`;
  return `${row.label}: ${held}, mean score ${row.mean_score.toFixed(1)} from ${
    row.rated_count
  } rated`;
}

const shown = 5;

/** The leading key as a ranked list: rank in serif, covers fanned, the leader big. */
export function RankedSection({
  number,
  title,
  type,
  insightKey,
  rows,
  suppressed,
  showSuppressed,
  onToggleSuppressed,
  noun,
  hrefFor,
}: {
  number: number;
  title: string;
  type: string;
  insightKey: string;
  rows: InsightRow[];
  suppressed: Array<{ label: string; count: number }>;
  showSuppressed: boolean;
  onToggleSuppressed: () => void;
  noun: Noun;
  hrefFor: HrefFor;
}) {
  const [sort, setSort] = useState<InsightSort>("count");
  const [open, setOpen] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const panelId = useId();
  const { placed, unplaced } = orderRows(rows, sort, 2);
  const visible = all ? placed : placed.slice(0, shown);
  const leader = placed[0];

  return (
    <Section
      number={number}
      title={title}
      aside={
        <div role="group" aria-label="Order" className="mt-2 flex gap-4">
          {(
            [
              ["count", "Most held"],
              ["score", "Best rated"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={sort === value}
              onClick={() => {
                setSort(value);
                setOpen(null);
              }}
              className={cn(
                "min-h-11 text-sm underline-offset-[6px] focus-ring",
                sort === value
                  ? "text-foreground underline decoration-primary decoration-2"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      }
    >
      {leader ? (
        <Prose
          segments={rankedSentence(leader, sort, noun)}
          className={sentenceClass}
        />
      ) : (
        <p className="text-muted-foreground">
          Nothing is rated enough to order by score yet.
        </p>
      )}
      <ol className="mt-6">
        {visible.map((row, index) => {
          const expanded = open === row.key;
          const panel = `${panelId}-${index}`;
          const lead = index === 0;
          return (
            <li key={row.key} className="border-b border-muted">
              <button
                type="button"
                aria-label={rowLabel(row, noun)}
                aria-expanded={expanded}
                aria-controls={panel}
                onClick={() => setOpen(expanded ? null : row.key)}
                className={cn(
                  "grid w-full grid-cols-[2.5rem_auto_minmax(0,1fr)_auto] items-center gap-4 rounded-md py-3 text-left transition-colors hover:bg-surface focus-ring md:gap-6",
                  expanded && "bg-surface",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "text-right font-display tabular-nums text-muted-foreground",
                    lead ? "text-5xl" : "text-3xl",
                  )}
                >
                  {index + 1}
                </span>
                <span aria-hidden="true" className="flex">
                  {row.covers.slice(0, 3).map((src, coverIndex) => (
                    <CoverImage
                      key={src}
                      src={src}
                      alt=""
                      className={cn(
                        "rounded-sm object-cover shadow-md ring-2 ring-background",
                        lead ? "h-20 w-14 md:h-24 md:w-16" : "h-14 w-10",
                        coverIndex > 0 && (lead ? "-ml-8" : "-ml-6"),
                        coverIndex === 1 && "rotate-3",
                        coverIndex === 2 && "-rotate-2",
                      )}
                      placeholderClassName={cn(
                        "rounded-sm ring-2 ring-background",
                        lead ? "h-20 w-14 md:h-24 md:w-16" : "h-14 w-10",
                        coverIndex > 0 && (lead ? "-ml-8" : "-ml-6"),
                      )}
                    />
                  ))}
                </span>
                <span className="min-w-0">
                  <span
                    className={cn(
                      "block font-medium",
                      lead
                        ? "line-clamp-2 font-display text-2xl leading-tight md:text-3xl"
                        : "truncate text-base md:text-lg",
                    )}
                  >
                    {row.label}
                  </span>
                  <span className="block text-sm text-muted-foreground">
                    {noun(row.count)}
                  </span>
                </span>
                <span
                  className={cn(
                    scoreChipShape,
                    "min-w-11 text-center",
                    lead && "px-2.5 py-1 text-lg",
                    meanScoreChipClass(row.mean_score),
                  )}
                >
                  {row.mean_score !== null ? row.mean_score.toFixed(1) : "—"}
                </span>
              </button>
              {expanded && (
                <InsightsMembers
                  id={panel}
                  type={type}
                  insightKey={insightKey}
                  value={row.key}
                  count={row.count}
                  href={hrefFor(row)}
                />
              )}
            </li>
          );
        })}
      </ol>
      <div className="mt-3 flex flex-wrap gap-x-6 text-sm text-muted-foreground">
        {placed.length > shown && (
          <button
            type="button"
            onClick={() => setAll((value) => !value)}
            className="min-h-11 underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
          >
            {all ? "Show fewer" : `Show ${placed.length - shown} more`}
          </button>
        )}
        {sort === "score" && unplaced.length > 0 && (
          <span className="flex min-h-11 items-center">
            {unplaced.length} not rated enough to place
          </span>
        )}
        {suppressed.length > 0 && (
          <button
            type="button"
            onClick={onToggleSuppressed}
            className="min-h-11 underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
          >
            {showSuppressed
              ? `Leave out ${suppressed.map((row) => row.label).join(", ")}`
              : `${suppressed.map((row) => `${row.label} (${row.count})`).join(", ")} left out — include`}
          </button>
        )}
      </div>
    </Section>
  );
}

const termLimit = 24;

/** A key with many values, typeset by weight: each term opens the library on it. */
export function TermsSection({
  number,
  title,
  rows,
  hrefFor,
}: {
  number: number;
  title: string;
  rows: InsightRow[];
  hrefFor: HrefFor;
}) {
  const [all, setAll] = useState(false);
  const ordered = [...rows].sort(
    (a, b) => b.count - a.count || a.key.localeCompare(b.key),
  );
  const max = ordered[0]?.count ?? 1;
  const visible = all ? ordered : ordered.slice(0, termLimit);
  return (
    <Section number={number} title={title}>
      <Prose segments={termsSentence(ordered)} className={sentenceClass} />
      <ul className="mt-6 flex max-w-3xl flex-wrap items-baseline gap-x-5 gap-y-1 font-display">
        {visible.map((row) => (
          <li key={row.key}>
            <Link
              to={hrefFor(row)}
              aria-label={`${row.label}: ${row.count}`}
              className={cn(
                "inline-flex min-h-11 items-baseline leading-none decoration-primary decoration-2 underline-offset-4 hover:underline focus-ring",
                termSize(row.count, max),
                row.count === 1 && "text-muted-foreground",
              )}
            >
              {row.label}
              <sup className="ml-0.5 font-sans text-[11px] text-muted-foreground">
                {row.count}
              </sup>
            </Link>
          </li>
        ))}
      </ul>
      {ordered.length > termLimit && (
        <button
          type="button"
          onClick={() => setAll((value) => !value)}
          className="mt-2 min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
        >
          {all ? "Show fewer" : `And ${ordered.length - termLimit} more`}
        </button>
      )}
    </Section>
  );
}

/** The chronology key at either grain, as short bars, one link each. */
export function ChronologySection({
  number,
  title,
  coarse,
  fine,
  fineLabel,
  earliest,
  noun,
  hrefFor,
}: {
  number: number;
  title: string;
  coarse: { key: string; rows: InsightRow[] };
  fine?: { key: string; rows: InsightRow[] };
  fineLabel: string;
  earliest: InsightSummary["earliest"];
  noun: Noun;
  hrefFor: (key: string, row: Pick<InsightRow, "key" | "label">) => string;
}) {
  const [grain, setGrain] = useState<"coarse" | "fine">("coarse");
  const buckets = chronologyBuckets(coarse.rows);
  if (buckets.length === 0) return null;
  const active = grain === "fine" && fine ? fine : coarse;
  const bars =
    active === coarse
      ? buckets.map((bucket) => ({
          key: String(bucket.decade),
          label: bucket.label,
          count: bucket.count,
        }))
      : [...active.rows]
          .sort((a, b) => Number(a.key) - Number(b.key))
          .map((row) => ({ key: row.key, label: row.label, count: row.count }));
  const max = Math.max(...bars.map((bar) => bar.count), 1);
  const lead = Math.max(...buckets.map((bucket) => bucket.count));

  return (
    <Section
      number={number}
      title={title}
      aside={
        fine && (
          <div role="group" aria-label="Grain" className="mt-2 flex gap-4">
            {(
              [
                ["coarse", title],
                ["fine", fineLabel],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={grain === value}
                onClick={() => setGrain(value)}
                className={cn(
                  "min-h-11 text-sm underline-offset-[6px] focus-ring",
                  grain === value
                    ? "text-foreground underline decoration-primary decoration-2"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        )
      }
    >
      <Prose
        segments={chronologySentence(buckets, earliest)}
        className={sentenceClass}
      />
      <div className="mt-6 overflow-x-auto pb-1">
        <ul className="flex h-28 min-w-0 max-w-2xl items-end gap-1.5">
          {bars.map((bar) => (
            <li
              key={bar.key}
              className="flex h-full min-w-6 flex-1 flex-col items-center justify-end gap-1"
            >
              {bar.count > 0 ? (
                <Link
                  to={hrefFor(active.key, bar)}
                  aria-label={`${bar.label}: ${noun(bar.count)}`}
                  className="group flex h-full w-full flex-col items-center justify-end gap-1 focus-ring"
                >
                  <span className="text-[11px] tabular-nums text-muted-foreground">
                    {bar.count}
                  </span>
                  <span
                    style={{
                      height: `${Math.max(6, (bar.count / max) * 100)}%`,
                    }}
                    className={cn(
                      "w-full rounded-sm transition-colors group-hover:bg-primary-deep",
                      active === coarse && bar.count === lead
                        ? "bg-primary-deep"
                        : "bg-primary",
                    )}
                  />
                </Link>
              ) : (
                <span aria-hidden="true" className="h-0.5 w-full bg-border" />
              )}
              <span className="whitespace-nowrap text-[11px] text-muted-foreground">
                {bar.label}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  );
}

const shareFill = [
  "bg-primary-deep",
  "bg-primary",
  "bg-score-mid",
  "bg-muted-foreground",
  "bg-border",
  "bg-muted",
];

/** A key with a handful of values, as one proportional bar. */
export function SharesSection({
  number,
  title,
  rows,
  hrefFor,
}: {
  number: number;
  title: string;
  rows: InsightRow[];
  hrefFor: HrefFor;
}) {
  const ordered = [...rows].sort((a, b) => b.count - a.count);
  const total = ordered.reduce((sum, row) => sum + row.count, 0);
  return (
    <Section number={number} title={title}>
      <Prose segments={shareSentence(ordered)} className={sentenceClass} />
      <div
        role="img"
        aria-label={ordered
          .map(
            (row) => `${row.label} ${Math.round((row.count / total) * 100)}%`,
          )
          .join(", ")}
        className="mt-6 flex h-3.5 max-w-xl gap-0.5 overflow-hidden rounded-full"
      >
        {ordered.map((row, index) => (
          <span
            key={row.key}
            style={{ width: `${(row.count / total) * 100}%` }}
            className={shareFill[index % shareFill.length]}
          />
        ))}
      </div>
      <ul className="mt-2 flex max-w-xl flex-wrap gap-x-6 text-sm text-muted-foreground">
        {ordered.map((row, index) => (
          <li key={row.key}>
            <Link
              to={hrefFor(row)}
              className="inline-flex min-h-11 items-center gap-2 hover:text-foreground focus-ring"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "h-2.5 w-2.5 rounded-full",
                  shareFill[index % shareFill.length],
                )}
              />
              <span className="font-semibold text-foreground">{row.label}</span>
              {row.count}
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}

const restLimit = 8;

/** Keys with little to say, one line each. */
export function RestSection({
  number,
  keys,
  hrefFor,
}: {
  number: number;
  keys: Array<{ name: string; label: string; rows: InsightRow[] }>;
  hrefFor: (key: string, row: Pick<InsightRow, "key" | "label">) => string;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (keys.length === 0) return null;
  return (
    <Section number={number} title="And the rest">
      <dl className="flex max-w-3xl flex-col gap-6">
        {keys.map(({ name, label, rows }) => {
          const ordered = [...rows].sort(
            (a, b) => b.count - a.count || a.key.localeCompare(b.key),
          );
          const visible = open === name ? ordered : ordered.slice(0, restLimit);
          return (
            <div key={name}>
              <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                {label}
              </dt>
              <dd className="mt-1 flex flex-wrap items-center gap-x-1 text-base">
                {rows.length === 0 && (
                  <span className="text-muted-foreground">
                    Nothing recorded yet.
                  </span>
                )}
                {visible.map((row, index) => (
                  <span key={row.key} className="inline-flex items-center">
                    {index > 0 && (
                      <span
                        aria-hidden="true"
                        className="mr-1 text-muted-foreground"
                      >
                        ·
                      </span>
                    )}
                    <Link
                      to={hrefFor(name, row)}
                      className={cn(
                        "inline-flex min-h-11 items-center gap-1 hover:underline focus-ring",
                        row.count > 1 && "font-semibold",
                      )}
                    >
                      {row.label}
                      <span className="font-normal text-muted-foreground">
                        {row.count}
                      </span>
                    </Link>
                  </span>
                ))}
                {ordered.length > restLimit && (
                  <button
                    type="button"
                    onClick={() => setOpen(open === name ? null : name)}
                    className="ml-2 min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
                  >
                    {open === name
                      ? "Show fewer"
                      : `and ${ordered.length - restLimit} more`}
                  </button>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </Section>
  );
}
