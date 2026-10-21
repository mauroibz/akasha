import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { setGoal, type Goal, type GoalPeriod } from "@/api/goals";
import { queryKeys } from "@/api/keys";
import type { ItemType } from "@/api/library";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { goalDomains } from "@/features/goals/goals";
import { cn } from "@/lib/utils";

/**
 * Setting a gentle goal (Sprint 104, DEC-169): which library, how many, a month or
 * a year, and whether to offer picks. The copy says the one rule that makes it
 * gentle: months count together.
 */
export function GoalDialog({
  open,
  onOpenChange,
  types,
  initial,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  types: ItemType[];
  /** The goal being changed; absent when setting a new one. */
  initial?: Goal;
}) {
  const domains = goalDomains(types);
  const [itemType, setItemType] = useState(
    initial?.item_type ?? domains[0]?.id ?? "",
  );
  const [count, setCount] = useState(initial?.count ?? 2);
  const [period, setPeriod] = useState<GoalPeriod>(initial?.period ?? "month");
  const [suggest, setSuggest] = useState(initial?.suggest ?? true);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!open) return;
    setItemType(initial?.item_type ?? domains[0]?.id ?? "");
    setCount(initial?.count ?? 2);
    setPeriod(initial?.period ?? "month");
    setSuggest(initial?.suggest ?? true);
    // Reset only when the dialog opens; `domains` is derived on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initial]);

  const save = useMutation({
    mutationFn: () => setGoal(itemType, { count, period, suggest }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.goals });
      onOpenChange(false);
    },
  });

  const plural = (
    domains.find((domain) => domain.id === itemType)?.plural_label ?? "items"
  ).toLowerCase();
  const yearly = period === "month" ? count * 12 : count;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl font-medium">
            A gentle goal
          </DialogTitle>
          <DialogDescription>
            Something to aim at, never something to keep up with. No streaks and
            no reminders.
          </DialogDescription>
        </DialogHeader>

        {!initial && domains.length > 1 && (
          <fieldset className="mt-2">
            <legend className="mb-3 text-sm font-semibold">For</legend>
            <div className="flex flex-wrap gap-2">
              {domains.map((domain) => (
                <button
                  key={domain.id}
                  type="button"
                  aria-pressed={domain.id === itemType}
                  onClick={() => setItemType(domain.id)}
                  className={cn(
                    "min-h-11 rounded-full border-[1.5px] px-4 text-sm font-medium transition-colors focus-ring",
                    domain.id === itemType
                      ? "border-foreground bg-foreground text-background"
                      : "border-border bg-surface-raised hover:border-foreground/40",
                  )}
                >
                  {domain.plural_label ?? domain.label}
                </button>
              ))}
            </div>
          </fieldset>
        )}

        <fieldset className="mt-4">
          <legend className="mb-3 text-sm font-semibold">How many</legend>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <div className="flex items-center gap-4">
              <button
                type="button"
                aria-label="One fewer"
                disabled={count <= 1}
                onClick={() => setCount((value) => Math.max(1, value - 1))}
                className="h-14 w-14 rounded-full border-[1.5px] border-border bg-surface-raised text-2xl focus-ring disabled:opacity-40"
              >
                −
              </button>
              <output
                aria-live="polite"
                aria-label={`${count} ${plural}`}
                className="min-w-16 text-center font-display text-7xl leading-none text-primary tabular-nums"
              >
                {count}
              </output>
              <button
                type="button"
                aria-label="One more"
                disabled={count >= 999}
                onClick={() => setCount((value) => Math.min(999, value + 1))}
                className="h-14 w-14 rounded-full border-[1.5px] border-border bg-surface-raised text-2xl focus-ring disabled:opacity-40"
              >
                +
              </button>
            </div>
            <div
              role="group"
              aria-label="Period"
              className="flex gap-1 rounded-lg bg-muted p-1"
            >
              {(["month", "year"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={period === value}
                  onClick={() => setPeriod(value)}
                  className={cn(
                    "min-h-10 rounded-md px-4 text-sm font-medium focus-ring",
                    period === value
                      ? "bg-surface-raised text-foreground shadow-sm"
                      : "text-muted-foreground",
                  )}
                >
                  a {value}
                </button>
              ))}
            </div>
          </div>
          <p className="mt-4 font-display text-lg leading-snug text-foreground/85">
            {period === "month"
              ? `About ${yearly} ${plural} in the year. Months count together, so more next month makes up for fewer this one.`
              : `${yearly} ${plural} across the year, at whatever pace the year has.`}
          </p>
        </fieldset>

        <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl bg-background p-4">
          <input
            type="checkbox"
            checked={suggest}
            onChange={(event) => setSuggest(event.target.checked)}
            className="mt-0.5 h-5 w-5 accent-[hsl(var(--primary-text))]"
          />
          <span>
            <span className="block text-sm font-semibold">
              Suggest what to start next
            </span>
            <span className="mt-0.5 block text-sm text-muted-foreground">
              A few picks from what is waiting. Skip them freely.
            </span>
          </span>
        </label>

        {save.isError && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {save.error.message}
          </p>
        )}

        <DialogFooter className="mt-4">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => save.mutate()}
            disabled={!itemType || save.isPending}
          >
            {initial ? "Save goal" : "Set goal"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
