import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import {
  deleteGoal,
  getGoalPicks,
  getGoalProgress,
  type Goal,
  type GoalPick,
} from "@/api/goals";
import { queryKeys } from "@/api/keys";
import { patchEntry, type ItemType } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import {
  calendarPlaces,
  goalSentence,
  type CalendarMonth,
  type Place,
} from "@/features/goals/goals";
import { Prose } from "@/features/insights/sections";
import { cn } from "@/lib/utils";

/**
 * One domain's goal on the Diary (Sprint 104, DEC-169): the year so far as a large
 * numeral, one sentence, and the calendar of lights — after Simone Giertz's
 * Everyday Calendar, a light for each thing finished, in its month. Unlit places
 * are plain, never red. Below it, when the goal asks for them, a few picks from
 * what is waiting.
 */
export function GoalBand({
  goal,
  year,
  types,
  onChange,
}: {
  goal: Goal;
  year: number;
  types: ItemType[];
  onChange: () => void;
}) {
  const headingId = useId();
  const queryClient = useQueryClient();
  const progress = useQuery({
    queryKey: queryKeys.goalProgress(goal.item_type, year),
    queryFn: ({ signal }) => getGoalProgress(goal.item_type, year, signal),
  });
  const remove = useMutation({
    mutationFn: () => deleteGoal(goal.item_type),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: queryKeys.goals }),
  });
  const domain = types.find((type) => type.id === goal.item_type);
  const plural = (domain?.plural_label ?? "items").toLowerCase();
  const today = new Date();
  const current = year === today.getFullYear();

  if (!progress.data) return null;
  const calendar = calendarPlaces(progress.data.months, goal, year, today);
  const described = calendar
    .map((month) => `${month.name} ${progress.data.months[month.index]}`)
    .join(", ");

  return (
    <section
      aria-labelledby={headingId}
      data-goal-band={goal.item_type}
      className="mt-8 rounded-2xl bg-surface px-5 py-7 md:px-10 md:py-9"
    >
      <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-12">
        <div>
          <h2
            id={headingId}
            className="text-sm font-medium text-muted-foreground"
          >
            Your {year} {plural}
          </h2>
          <p className="mt-2 font-display text-5xl leading-none md:text-6xl">
            <span className="text-primary tabular-nums">
              {progress.data.total}
            </span>{" "}
            <span className="text-3xl text-foreground/80 md:text-4xl">
              so far
            </span>
          </p>
          <Prose
            segments={goalSentence(goal, progress.data, today)}
            className="mt-4 max-w-[34ch] font-display text-lg leading-snug text-foreground/85 md:text-xl"
          />
          <div className="mt-3 flex gap-5">
            <button
              type="button"
              onClick={onChange}
              className="min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
            >
              Change goal
            </button>
            <button
              type="button"
              onClick={() => remove.mutate()}
              className="min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
            >
              Remove goal
            </button>
          </div>
        </div>
        <Calendar
          calendar={calendar}
          label={`A light for each of your ${plural} finished in ${year}: ${described}.`}
        />
      </div>
      {goal.suggest && current && <Picks goal={goal} types={types} />}
    </section>
  );
}

const placeClass: Record<Place, string> = {
  lit: "bg-primary shadow-[0_0_0_3px_hsl(var(--primary)/0.16),0_0_14px_hsl(var(--primary)/0.55)]",
  open: "bg-muted",
  now: "border-[1.5px] border-dashed border-primary",
  ahead: "border-[1.5px] border-dashed border-border",
};

function Calendar({
  calendar,
  label,
}: {
  calendar: CalendarMonth[];
  label: string;
}) {
  return (
    <div
      role="img"
      aria-label={label}
      className="flex items-end gap-[5px] md:gap-2"
    >
      {calendar.map((month) => (
        <div key={month.index} className="flex flex-col items-center gap-2">
          {month.more > 0 && (
            <span className="text-[10px] text-muted-foreground">
              +{month.more}
            </span>
          )}
          <div className="flex flex-col-reverse gap-[5px] md:gap-1.5">
            {month.places.map((place, slot) => (
              <span
                key={slot}
                data-place={place}
                className={cn(
                  "block h-[22px] w-5 rounded-[7px] md:h-[30px] md:w-7 md:rounded-[9px]",
                  placeClass[place],
                )}
              />
            ))}
          </div>
          <span
            className={cn(
              "text-[11px]",
              month.current
                ? "font-semibold text-foreground"
                : "text-muted-foreground",
            )}
          >
            {month.short}
          </span>
        </div>
      ))}
    </div>
  );
}

const tilt = ["-rotate-2", "rotate-[1.5deg]", "-rotate-1", "rotate-2"];

/**
 * A few picks from what is waiting, each with its reason. *Something else* swaps a
 * pick for the next one; *Start* moves it to the domain's own in-progress status,
 * and is absent where the domain has none.
 */
function Picks({ goal, types }: { goal: Goal; types: ItemType[] }) {
  const queryClient = useQueryClient();
  const picks = useQuery({
    queryKey: queryKeys.goalPicks(goal.item_type),
    queryFn: ({ signal }) => getGoalPicks(goal.item_type, signal),
  });
  const [skipped, setSkipped] = useState<number[]>([]);
  const domain = types.find((type) => type.id === goal.item_type);
  const startStatus = domain?.statuses.find((status) => status.in_progress);
  const start = useMutation({
    mutationFn: (pick: GoalPick) =>
      patchEntry(pick.entry.id, { status: startStatus!.value }),
    onSuccess: (_saved, pick) => {
      toast.success(`${pick.entry.item.title} is under way`);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.goalPicks(goal.item_type),
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.now });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    },
    onError: () => toast.error("That could not be started"),
  });

  const all = picks.data ?? [];
  const shown = all
    .filter((pick) => !skipped.includes(pick.entry.id))
    .slice(0, 2);
  if (shown.length === 0) return null;
  const month = new Intl.DateTimeFormat("en", { month: "long" }).format(
    new Date(),
  );

  return (
    <div className="mt-10 border-t border-border pt-8">
      <h3 className="font-display text-2xl font-medium md:text-3xl">
        Something for the rest of {month}
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        From what is waiting. Take one, both or neither.
      </p>
      <ul className="-mx-1 mt-6 flex gap-8 overflow-x-auto px-1 pb-2 md:grid md:grid-cols-2 md:overflow-visible">
        {shown.map((pick, index) => (
          <li
            key={pick.entry.id}
            className="flex w-[17rem] shrink-0 gap-5 md:w-auto"
          >
            <Link
              to={`/books/${pick.entry.id}`}
              aria-label={`Open ${pick.entry.item.title}`}
              className={cn(
                "shrink-0 rounded-md focus-ring",
                tilt[index % tilt.length],
              )}
            >
              <CoverImage
                src={pick.entry.item.cover_url}
                alt=""
                className="h-[11.25rem] w-[7.5rem] rounded-[3px_8px_8px_3px] object-cover shadow-[inset_5px_0_0_rgba(0,0,0,0.18),0_18px_30px_-12px_rgba(28,25,23,0.45)] md:h-60 md:w-40"
                placeholderClassName="h-[11.25rem] w-[7.5rem] rounded-md md:h-60 md:w-40"
              />
            </Link>
            <div className="min-w-0 pt-1">
              <h4 className="font-display text-xl font-medium leading-tight md:text-2xl">
                {pick.entry.item.title}
              </h4>
              {pick.entry.item.creator && (
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {pick.entry.item.creator}
                </p>
              )}
              <p className="mt-3 text-sm leading-relaxed text-foreground/85">
                {reason(pick, types)}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
                {startStatus && (
                  <Button
                    onClick={() => start.mutate(pick)}
                    disabled={start.isPending}
                  >
                    Start
                  </Button>
                )}
                <button
                  type="button"
                  onClick={() => setSkipped((ids) => [...ids, pick.entry.id])}
                  className="min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
                >
                  Something else
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// `date_added` is stored in UTC; reading its month locally would move a midnight
// addition into the month before, west of Greenwich.
const since = new Intl.DateTimeFormat("en", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

function reason(pick: GoalPick, types: ItemType[]): string {
  if (pick.reason === "creator" && pick.creator) {
    const plural = (
      types.find((type) => type.id === pick.entry.item.type)?.plural_label ??
      "items"
    ).toLowerCase();
    const average =
      pick.mean_score !== null && pick.mean_score !== undefined
        ? `, whose ${plural} you rate ${pick.mean_score.toFixed(1)} on average`
        : "";
    return `By ${pick.creator}${average}.`;
  }
  if (pick.since) return `Waiting since ${since.format(new Date(pick.since))}.`;
  return "Waiting for you.";
}
