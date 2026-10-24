import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { setGoal } from "@/api/goals";
import { queryKeys } from "@/api/keys";
import type { ItemType } from "@/api/library";
import { Button } from "@/components/ui/button";
import { suggestedCounts } from "@/features/goals/goals";
import { cn } from "@/lib/utils";

/**
 * No goal yet (Sprint 127, DEC-179, mockup 3A): the Diary opens with the year so far
 * and three goals said as paces, one tap to set one. *Another number* opens the full
 * dialog, which chooses the library and a monthly goal.
 */
export function GoalInvite({
  domain,
  done,
  year,
  onOther,
}: {
  domain: ItemType;
  done: number;
  year: number;
  onOther: () => void;
}) {
  const headingId = useId();
  const queryClient = useQueryClient();
  const picks = suggestedCounts(done);
  const [count, setCount] = useState(picks[1].count);
  const plural = (domain.plural_label ?? domain.label).toLowerCase();
  const save = useMutation({
    mutationFn: () =>
      setGoal(domain.id, { count, period: "year", suggest: true }),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: queryKeys.goals }),
  });
  return (
    <section
      aria-labelledby={headingId}
      className="mt-8 rounded-2xl bg-surface px-5 py-7 md:px-10 md:py-9"
    >
      <p className="text-sm font-medium text-muted-foreground">
        You've finished {done}{" "}
        {done === 1 ? domain.label.toLowerCase() : plural} in {year}
      </p>
      <h2
        id={headingId}
        className="mt-2 font-display text-3xl leading-tight md:text-4xl"
      >
        Want something to aim at this year?
      </h2>
      <div className="mt-6 grid max-w-xl grid-cols-3 gap-2 sm:gap-3">
        {picks.map((pick) => (
          <button
            key={pick.count}
            type="button"
            aria-pressed={count === pick.count}
            onClick={() => setCount(pick.count)}
            className={cn(
              "rounded-xl border px-2 pb-3 pt-2.5 text-center transition-colors focus-ring",
              count === pick.count
                ? "border-primary bg-primary/15"
                : "border-border bg-background hover:bg-accent",
            )}
          >
            <span className="block font-display text-3xl tabular-nums leading-none">
              {pick.count}
            </span>
            <span className="mt-1.5 block text-xs text-muted-foreground">
              {pick.words}
            </span>
          </button>
        ))}
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2">
        <Button
          className="rounded-full px-6"
          disabled={save.isPending}
          onClick={() => save.mutate()}
        >
          Aim for {count}
        </Button>
        <button
          type="button"
          onClick={onOther}
          className="min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
        >
          Another number
        </button>
      </div>
      <p className="mt-3 text-sm text-muted-foreground">
        No streaks and no reminders. Being behind is only room left.
      </p>
      {save.error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {save.error.message}
        </p>
      )}
    </section>
  );
}
