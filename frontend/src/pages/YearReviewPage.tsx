import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getYearReview } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { Loading } from "@/components/ui/skeleton";
import { Prose, RatingSection, Section } from "@/features/insights/sections";
import { countLabel } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import {
  bestSentence,
  changesSentence,
  leadSentence,
  monthsSentence,
} from "@/features/review/prose";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

const MONTH = new Intl.DateTimeFormat(undefined, { month: "long" });
const SHORT = new Intl.DateTimeFormat(undefined, { month: "narrow" });
const monthName = (index: number) => MONTH.format(new Date(2000, index, 1));
const monthOf = (at: string) => monthName(Number(at.slice(5, 7)) - 1);

const sentence = "max-w-[40ch] font-display text-xl leading-snug md:text-2xl";

/**
 * The year in review (Sprint 120, DEC-178): one page per year, reached from the
 * Diary, read back in the Insights style. Computed when opened, across every library
 * as the Diary is, so a score changed later changes the page too.
 */
export function YearReviewPage() {
  const year = Number(useParams().year);
  const itemTypes = useItemTypes();
  const review = useQuery({
    queryKey: ["diary", year, "review"],
    queryFn: ({ signal }) => getYearReview(year, signal),
    enabled: Number.isInteger(year),
  });
  const noun = (type: string, count: number) =>
    countLabel(count, type, itemTypes.data);

  if (review.isPending)
    return (
      <main className="mx-auto w-full max-w-5xl px-5 py-8">
        <Loading label="Reading the year back…" />
      </main>
    );
  if (review.isError)
    return (
      <main className="mx-auto w-full max-w-5xl px-5 py-8">
        <p role="alert" className="text-destructive">
          The year could not be read back.
        </p>
      </main>
    );
  const data = review.data;
  const sections: Array<{ title: string; body: React.ReactNode }> = [];
  const best = bestSentence(
    data.best.map((row) => ({
      title: row.entry.item.title,
      score: row.score,
      month: monthOf(row.at),
    })),
  );
  if (best)
    sections.push({
      title: "The best of it",
      body: (
        <>
          <Prose segments={best} className={sentence} />
          <ul className="mt-6 grid max-w-xl grid-cols-3 gap-3 sm:grid-cols-5">
            {data.best.map((row) => (
              <li key={row.entry.id}>
                <Link
                  to={`/books/${row.entry.id}`}
                  className="block rounded-md focus-ring"
                >
                  <CoverImage
                    src={row.entry.item.cover_url ?? null}
                    alt=""
                    className="aspect-[2/3] w-full rounded-md object-cover"
                  />
                  <span className="mt-1.5 flex items-center justify-between gap-1 text-xs">
                    <span className="truncate">{row.entry.item.title}</span>
                    <span
                      className={cn(scoreChipShape, scoreChipClass(row.score))}
                    >
                      {row.score}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      ),
    });
  const months = monthsSentence(data.months, monthName);
  if (months) {
    const most = Math.max(...data.months, 1);
    sections.push({
      title: "Month by month",
      body: (
        <>
          <Prose segments={months} className={sentence} />
          <div
            role="img"
            aria-label={`Finished each month: ${data.months
              .map((count, index) => `${monthName(index)} ${count}`)
              .join(", ")}.`}
            className="mt-6 flex h-20 max-w-md items-end gap-1.5"
          >
            {data.months.map((count, index) => (
              <div
                key={index}
                className="flex h-full flex-1 flex-col items-center justify-end gap-1"
              >
                <span className="text-[10px] tabular-nums text-muted-foreground">
                  {count}
                </span>
                <div
                  className={cn(
                    "w-full rounded-sm",
                    count ? "bg-primary" : "bg-border",
                  )}
                  style={{
                    height: count
                      ? `${Math.max(8, (count / most) * 100)}%`
                      : "2px",
                  }}
                />
                <span className="text-[11px] leading-none text-muted-foreground">
                  {SHORT.format(new Date(2000, index, 1))}
                </span>
              </div>
            ))}
          </div>
        </>
      ),
    });
  }
  const changed = changesSentence(
    data.changes.map((change) => ({
      title: change.entry.item.title,
      previous: change.previous,
      score: change.score,
      reason: change.reason,
    })),
  );
  if (changed)
    sections.push({
      title: "What you changed your mind about",
      body: (
        <>
          <Prose segments={changed} className={sentence} />
          <ul className="mt-5 max-w-xl space-y-2 text-sm">
            {data.changes.map((change, index) => (
              <li key={index} className="flex flex-wrap items-center gap-2">
                <span className="font-display text-lg">
                  {change.entry.item.title}
                </span>
                <span className="tabular-nums">
                  {change.previous} → {change.score ?? "no score"}
                </span>
                <span className="text-muted-foreground">
                  {change.reason === "reread" ? "after a reread" : "with time"}{" "}
                  · {monthOf(change.at)}
                </span>
                {change.note && (
                  <span className="w-full font-display italic">
                    “{change.note}”
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      ),
    });
  if (data.quote)
    sections.push({
      title: "In your words",
      body: (
        <>
          <p className="max-w-[36ch] font-display text-2xl italic leading-snug">
            “{data.quote.text}”
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            <Link
              to={`/books/${data.quote.entry_id}`}
              className="underline-offset-4 hover:underline focus-ring"
            >
              {data.quote.title}
            </Link>
            , {monthOf(data.quote.at)}
          </p>
        </>
      ),
    });

  return (
    <main className="mx-auto w-full max-w-5xl px-5 py-8">
      <Link
        to="/diary"
        className="text-sm font-medium text-muted-foreground hover:text-foreground focus-ring"
      >
        ← Diary
      </Link>
      <h1 className="mt-3 font-display text-6xl font-medium tracking-tight md:text-7xl">
        {data.year}
      </h1>
      {data.finished === 0 ? (
        <p className={cn(sentence, "mt-6")}>
          Nothing was finished in {data.year}.
        </p>
      ) : (
        <>
          <Prose
            segments={leadSentence({
              counts: data.counts,
              finished: data.finished,
              scores: data.scores,
              leader: data.leader,
              noun,
            })}
            className={cn(sentence, "mt-6 max-w-[34ch] text-2xl md:text-3xl")}
          />
          <div className="mt-8">
            {sections.slice(0, 1).map((section) => (
              <Section key={section.title} number={1} title={section.title}>
                {section.body}
              </Section>
            ))}
            <RatingSection
              number={sections.length ? 2 : 1}
              counts={data.scores}
              unrated={0}
            />
            {sections.slice(1).map((section, index) => (
              <Section
                key={section.title}
                number={index + 3}
                title={section.title}
              >
                {section.body}
              </Section>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
