import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import { getNow, type LibraryEntry } from "@/api/library";
import { getLitDays, lightDay, unlightDay, type LitDay } from "@/api/litDays";
import { Cover } from "@/components/Cover";
import { cn } from "@/lib/utils";

import { daysOf, iso, longDay, type Span } from "./days";
import { DaySearch } from "./DaySearch";

export const spanKey = "akasha.journal.everyday";
const weekdays = ["M", "T", "W", "T", "F", "S", "S"];

function rememberedSpan(): Span {
  try {
    return localStorage.getItem(spanKey) === "week" ? "week" : "month";
  } catch {
    return "month";
  }
}

const plain =
  "min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring";
const filled =
  "min-h-11 rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground focus-ring disabled:opacity-50";

/**
 * Every day (Sprint 147, DEC-193): this week or this month as a grid of days, a
 * light for each day something was read, watched or finished, after Simone
 * Giertz's Every Day Calendar. Never the year. A day lights when progress is
 * logged or something is finished, and by hand: lighting one asks a single
 * question, what it was for, offering what is under way, and takes "nothing in
 * particular" for an answer. The owner: "it must be kept simple and calm". So
 * there is no amount, no note, no streak, and an unlit day is only unlit.
 */
export function EveryDay({ today = new Date() }: { today?: Date }) {
  const queryClient = useQueryClient();
  const [span, setSpan] = useState<Span>(rememberedSpan);
  const [open, setOpen] = useState<string | null>(null);
  const [changing, setChanging] = useState(false);
  const [chosen, setChosen] = useState<number[]>([]);
  // What *Something else* found: offered beside what is under way once chosen.
  const [extra, setExtra] = useState<LibraryEntry[]>([]);
  const [searching, setSearching] = useState(false);
  const { days, lead } = daysOf(span, today);
  const from = iso(days[0]);
  const to = iso(days[days.length - 1]);
  const lit = useQuery({
    queryKey: [...queryKeys.litDays, from, to],
    queryFn: ({ signal }) => getLitDays(from, to, signal),
    retry: false,
  });
  const now = useQuery({
    queryKey: queryKeys.now,
    queryFn: ({ signal }) => getNow(signal),
    retry: false,
    // Asked only when a day is being lit: it is what the question offers.
    enabled: open !== null,
  });
  const byDay = new Map<string, LitDay>(
    (Array.isArray(lit.data?.days) ? lit.data.days : []).map((row) => [
      row.day,
      row,
    ]),
  );
  const todayIso = iso(today);
  const done = () => {
    setOpen(null);
    setChanging(false);
    setChosen([]);
    setExtra([]);
    setSearching(false);
    void queryClient.invalidateQueries({ queryKey: queryKeys.litDays });
  };
  const light = useMutation({
    mutationFn: (day: string) => lightDay(day, chosen),
    onSuccess: done,
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "The day could not be lit",
      ),
  });
  const unlight = useMutation({
    mutationFn: (day: string) => unlightDay(day),
    onSuccess: done,
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "The day could not be unlit",
      ),
  });

  const choose = (next: Span) => {
    setSpan(next);
    setOpen(null);
    try {
      localStorage.setItem(spanKey, next);
    } catch {
      // Not remembered, still chosen.
    }
  };
  const count = days.filter((day) => byDay.has(iso(day))).length;
  const month = new Intl.DateTimeFormat("en-GB", { month: "long" }).format(
    today,
  );
  const said =
    span === "week"
      ? `${count} of 7 days lit this week`
      : `${count} ${count === 1 ? "day" : "days"} lit in ${month}`;

  const opened = open ? days.find((day) => iso(day) === open) : undefined;
  const openedLit = open ? byDay.get(open) : undefined;
  const asking = opened && (!openedLit || changing);
  const underWay = Array.isArray(now.data) ? now.data : [];
  const under = [
    ...underWay,
    ...extra.filter((entry) => !underWay.some((row) => row.id === entry.id)),
  ];
  const find = (entry: LibraryEntry) => {
    setExtra((rows) =>
      rows.some((row) => row.id === entry.id) ? rows : [...rows, entry],
    );
    setChosen((ids) => (ids.includes(entry.id) ? ids : [...ids, entry.id]));
  };
  const toggle = (entry: LibraryEntry) =>
    setChosen((ids) =>
      ids.includes(entry.id)
        ? ids.filter((id) => id !== entry.id)
        : [...ids, entry.id],
    );

  return (
    <div className="grid gap-6 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] md:items-start">
      <div>
        <div
          role="group"
          aria-label="Show"
          className="mb-3 inline-flex rounded-full bg-muted p-0.5"
        >
          {(
            [
              ["week", "This week"],
              ["month", "This month"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={span === value}
              onClick={() => choose(value)}
              className="min-h-11 rounded-full px-3.5 text-xs font-medium text-muted-foreground focus-ring aria-pressed:bg-surface-raised aria-pressed:text-foreground"
            >
              {label}
            </button>
          ))}
        </div>
        <div aria-hidden="true" className="mb-1.5 grid grid-cols-7 gap-1.5">
          {weekdays.map((letter, index) => (
            <span
              key={index}
              className="text-center text-[11px] text-muted-foreground"
            >
              {letter}
            </span>
          ))}
        </div>
        <ul aria-label={said} className="grid grid-cols-7 gap-1.5">
          {Array.from({ length: lead }, (_, index) => (
            <li key={`lead-${index}`} aria-hidden="true" />
          ))}
          {days.map((day) => {
            const key = iso(day);
            const row = byDay.get(key);
            const future = key > todayIso;
            const names = row?.entries.map((entry) => entry.item.title) ?? [];
            return (
              <li key={key}>
                <button
                  type="button"
                  data-day={key}
                  aria-pressed={Boolean(row)}
                  aria-current={key === todayIso ? "date" : undefined}
                  aria-label={`${longDay(day)}, ${
                    row
                      ? names.length
                        ? `lit for ${names.join(", ")}`
                        : "lit"
                      : future
                        ? "to come"
                        : "not lit"
                  }`}
                  disabled={future}
                  onClick={() => {
                    setOpen(open === key ? null : key);
                    setChanging(false);
                    setSearching(false);
                    setExtra(row?.entries ?? []);
                    setChosen(row?.entries.map((entry) => entry.id) ?? []);
                  }}
                  className={cn(
                    // 44px tall whatever the width: on a phone a seventh of the row is narrower.
                    "flex min-h-11 w-full items-center justify-center rounded-lg text-xs font-medium tabular-nums transition-colors focus-ring disabled:opacity-40",
                    row
                      ? "bg-primary text-primary-foreground shadow-[0_0_10px_hsl(var(--primary)/0.45)]"
                      : "bg-muted text-muted-foreground hover:text-foreground",
                    key === todayIso &&
                      "outline outline-2 outline-offset-2 outline-foreground",
                    open === key &&
                      "ring-2 ring-ring ring-offset-2 ring-offset-surface",
                  )}
                >
                  {day.getDate()}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="min-w-0">
        <p className="font-display text-3xl font-medium text-primary-text">
          {said}
        </p>
        {!opened && (
          <p className="mt-2 max-w-prose text-sm text-muted-foreground">
            A day lights when you log progress or finish something. Tap a day to
            light it yourself. An unlit day is only unlit: nothing counts
            streaks.
          </p>
        )}

        {opened && !asking && openedLit && (
          <div className="mt-3" role="group" aria-label={longDay(opened)}>
            <p className="font-medium">{longDay(opened)}</p>
            {openedLit.entries.length ? (
              <ul className="mt-2 flex flex-wrap gap-3">
                {openedLit.entries.map((entry) => (
                  <li key={entry.id} className="w-16">
                    <Link
                      to={`/books/${entry.id}`}
                      aria-label={`Open ${entry.item.title}`}
                      className="group block rounded focus-ring"
                    >
                      <Cover src={entry.item.cover_url} size="s" />
                      <span className="mt-1 block truncate text-xs">
                        {entry.item.title}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">
                Lit, for nothing in particular.
              </p>
            )}
            <div className="mt-2 flex flex-wrap gap-x-5">
              <button
                type="button"
                className={plain}
                onClick={() => setChanging(true)}
              >
                Change what it was for
              </button>
              <button
                type="button"
                className={plain}
                disabled={unlight.isPending}
                onClick={() => unlight.mutate(iso(opened))}
              >
                Unlight
              </button>
              <button
                type="button"
                className={plain}
                onClick={() => setOpen(null)}
              >
                Close
              </button>
            </div>
          </div>
        )}

        {asking && (
          <div className="mt-3" role="group" aria-label="What was it for?">
            <p className="font-medium">What was {longDay(opened)} for?</p>
            {under.length > 0 ? (
              <ul className="mt-2 flex flex-wrap gap-3">
                {under.map((entry) => (
                  <li key={entry.id} className="w-16">
                    <button
                      type="button"
                      aria-pressed={chosen.includes(entry.id)}
                      aria-label={entry.item.title}
                      onClick={() => toggle(entry)}
                      className="group block w-full rounded text-left focus-ring aria-pressed:outline aria-pressed:outline-2 aria-pressed:outline-offset-2 aria-pressed:outline-primary"
                    >
                      <Cover src={entry.item.cover_url} size="s" />
                      <span className="mt-1 block truncate text-xs">
                        {entry.item.title}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">
                {now.isPending
                  ? "Looking at what is under way…"
                  : "Nothing is under way. Find what it was for, or just light it."}
              </p>
            )}
            {searching && <DaySearch chosen={chosen} onChoose={find} />}
            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1">
              <button
                type="button"
                className={filled}
                disabled={light.isPending}
                onClick={() => light.mutate(iso(opened))}
              >
                {chosen.length ? "Light it" : "Just light it"}
              </button>
              {!searching && (
                <button
                  type="button"
                  className={plain}
                  onClick={() => setSearching(true)}
                >
                  Something else
                </button>
              )}
              <button
                type="button"
                className={plain}
                onClick={() => setOpen(null)}
              >
                Not now
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
