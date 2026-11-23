import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getGoals, type Goal } from "@/api/goals";
import { queryKeys } from "@/api/keys";
import { getDiary } from "@/api/library";
import { DomainStrip } from "@/components/DomainStrip";
import { useItemTypes } from "@/features/library/useItemTypes";
import { useShownItemTypes } from "@/features/media/useMedia";

import { GoalBand } from "./GoalBand";
import { GoalDialog } from "./GoalDialog";
import { GoalInvite } from "./GoalInvite";
import { goalDomains } from "./goals";

/**
 * This year's goals, as a widget of the Journal (Sprint 146, DEC-193): each goal's
 * slots and picks, or the invitation to set one, with the same parts the Diary
 * drew at its top (Sprints 104 and 127). Always the current year: a goal is for now.
 */
export function GoalWidget() {
  const itemTypes = useItemTypes();
  const types = Array.isArray(itemTypes.data) ? itemTypes.data : [];
  const diary = useQuery({
    queryKey: queryKeys.diary(undefined),
    queryFn: ({ signal }) => getDiary(undefined, signal),
  });
  const goals = useQuery({
    queryKey: queryKeys.goals,
    queryFn: ({ signal }) => getGoals(signal),
  });
  const [editing, setEditing] = useState<{ open: boolean; goal?: Goal }>({
    open: false,
  });
  const year = new Date().getFullYear();
  // The diary answers for the newest year with a finish; only this year's count.
  const months = diary.data?.year === year ? (diary.data?.months ?? []) : [];
  const finishedOf = (itemType: string) =>
    months.flatMap((month) =>
      month.entries.filter((entry) => entry.item.type === itemType),
    );
  const able = goalDomains(types);
  const invited = [...able].sort(
    (a, b) => finishedOf(b.id).length - finishedOf(a.id).length,
  )[0];
  const mine = Array.isArray(goals.data) ? goals.data : [];
  // The medium the invitation is for is the person's to choose (DEC-195): among the
  // media a goal can count, in their order, the one finished most to begin with.
  const shown = useShownItemTypes();
  // Their media first, then the rest: a goal can be set for a medium not begun yet,
  // and a medium nobody chose to turn off is not one to withhold.
  const first = (shown.data ?? []).filter((type) =>
    able.some((domain) => domain.id === type.id),
  );
  const offered = [
    ...first,
    ...able.filter((domain) => !first.some((type) => type.id === domain.id)),
  ];
  const [picked, setPicked] = useState<string | null>(null);
  const domain =
    offered.find((type) => type.id === picked) ??
    offered.find((type) => type.id === invited?.id) ??
    invited;

  if (goals.isPending) return null;
  return (
    <div>
      {mine.map((goal) => (
        <GoalBand
          key={goal.item_type}
          goal={goal}
          year={year}
          types={types}
          finished={finishedOf(goal.item_type)}
          onChange={() => setEditing({ open: true, goal })}
        />
      ))}
      {mine.length === 0 && domain && offered.length > 1 && (
        <DomainStrip
          label="A goal for"
          domains={offered.map((type) => ({
            id: type.id,
            label: type.plural_label ?? type.label,
          }))}
          value={domain.id}
          onChange={setPicked}
        />
      )}
      {mine.length === 0 && domain && (
        <GoalInvite
          // A fresh invitation per medium: its paces follow that medium's count.
          key={domain.id}
          domain={domain}
          done={finishedOf(domain.id).length}
          year={year}
          onOther={() => setEditing({ open: true })}
        />
      )}
      {mine.length === 0 && !domain && (
        <p className="text-sm text-muted-foreground">
          A goal counts what you finish in a year. Nothing you keep records
          finishing yet.
        </p>
      )}
      {mine.length > 0 && able.length > 0 && (
        <p className="mt-4 text-sm text-muted-foreground">
          <button
            type="button"
            onClick={() => setEditing({ open: true })}
            className="min-h-11 font-medium text-foreground underline decoration-primary decoration-2 underline-offset-4 focus-ring"
          >
            Add a goal for another library
          </button>
        </p>
      )}
      <GoalDialog
        open={editing.open}
        onOpenChange={(open) => setEditing((value) => ({ ...value, open }))}
        types={types}
        initial={editing.goal}
      />
    </div>
  );
}
