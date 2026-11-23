import { Link } from "react-router-dom";

import type { HomeGreeting } from "@/api/home";
import type { ItemType } from "@/api/library";

import { localDate } from "./year";

function plural(itemType: string, types: ItemType[] | undefined): string {
  const declared = (Array.isArray(types) ? types : []).find(
    (type) => type.id === itemType,
  );
  return (declared?.plural_label ?? "items").toLowerCase();
}

/**
 * The Library's first line (Sprints 130-131, DEC-183; a second-level heading since
 * Sprint 141, when the Library's own title became the page's): the day, what is under way and
 * for how long, the library in three numbers, and *Edit home*. What it names and the
 * goal beside it are of one library (the server picks the pair). "Day N of …" only when the entry has a
 * start date; without one the title stands alone.
 */
export function GreetingBar({
  greeting,
  types,
  onEdit,
}: {
  greeting: HomeGreeting;
  types: ItemType[] | undefined;
  /** Opens *Edit home*; absent on the first-run screen, which has nothing to arrange. */
  onEdit?: () => void;
}) {
  const today = localDate(greeting.today);
  const weekday = new Intl.DateTimeFormat("en", { weekday: "long" }).format(
    today,
  );
  const date = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
  }).format(today);
  const active = greeting.active;
  const year = today.getFullYear();
  return (
    <div className="flex flex-col gap-2 lg:flex-row lg:items-baseline lg:justify-between">
      <h2 className="min-w-0 font-display text-2xl font-medium leading-tight tracking-tight sm:text-3xl">
        {active ? (
          <>
            {weekday}. {active.day ? <>Day {active.day} of </> : null}
            <Link
              to={`/books/${active.entry.id}`}
              className="italic text-primary underline-offset-4 hover:underline focus-ring"
            >
              {active.entry.item.title}
            </Link>
            .
          </>
        ) : (
          <>
            {weekday}, {date}.
          </>
        )}
      </h2>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <div className="flex gap-1">
            <dt className="sr-only">Entries</dt>
            <dd>
              <span className="font-semibold tabular-nums text-foreground">
                {greeting.entries.toLocaleString()}
              </span>{" "}
              entries
            </dd>
          </div>
          {greeting.goals.map((goal) => (
            <div key={goal.item_type} className="flex gap-1">
              <dt className="sr-only">Goal</dt>
              <dd>
                <span className="font-semibold tabular-nums text-foreground">
                  {goal.count}
                </span>{" "}
                of {goal.target} {plural(goal.item_type, types)} in {year}
              </dd>
            </div>
          ))}
          <div className="flex gap-1">
            <dt className="sr-only">Pile</dt>
            <dd>
              <Link
                to="/pile"
                className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
              >
                <span className="font-semibold tabular-nums text-foreground">
                  {greeting.pile.toLocaleString()}
                </span>{" "}
                on the pile
              </Link>
            </dd>
          </div>
        </dl>
        {onEdit ? (
          <button
            type="button"
            onClick={onEdit}
            className="text-sm font-medium text-foreground underline-offset-4 hover:underline focus-ring"
          >
            Edit home
          </button>
        ) : null}
      </div>
    </div>
  );
}
