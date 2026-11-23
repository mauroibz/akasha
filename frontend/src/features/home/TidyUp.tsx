import { Link } from "react-router-dom";

import type { HomeTidy } from "@/api/home";
import type { ItemType } from "@/api/library";

import { HomeModule } from "./HomeModule";

/** Every status a domain declares finished: where "not scored" looks. */
function finishedStatuses(types: ItemType[] | undefined): string[] {
  const found = new Set<string>();
  for (const type of Array.isArray(types) ? types : [])
    for (const status of type.statuses)
      if (status.finished) found.add(status.value);
  return [...found];
}

/**
 * Small jobs (Sprint 131): pairs that look like one work, what has no cover, what
 * was finished without a score. Each count opens what resolves it: the duplicates
 * and covers decks, and the library filtered to the unscored. A count of nothing is
 * left out; the module is hidden when every count is.
 */
export function TidyUp({
  tidy,
  types,
  className,
}: {
  tidy: HomeTidy;
  types: ItemType[] | undefined;
  className?: string;
}) {
  const unscored = new URLSearchParams();
  for (const status of finishedStatuses(types))
    unscored.append("status", status);
  unscored.set("unscored", "true");
  const jobs = [
    {
      count: tidy.duplicates,
      label: "possible duplicate pairs",
      action: "Review",
      to: "/deck/duplicates",
    },
    {
      count: tidy.without_cover,
      label: "without a cover",
      action: "Find",
      to: "/deck/covers",
    },
    {
      count: tidy.unscored,
      label: "finished, not scored",
      action: "Score",
      to: `/library?${unscored.toString()}`,
    },
  ].filter((job) => job.count > 0);
  return (
    <HomeModule
      title="Tidy up"
      className={className}
      aside={
        <Link
          to="/deck"
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          All →
        </Link>
      }
    >
      <ul className="divide-y divide-border">
        {jobs.map((job) => (
          <li key={job.to}>
            <Link
              to={job.to}
              className="flex min-h-11 items-center gap-3 py-1.5 focus-ring"
            >
              <span className="font-display text-2xl tabular-nums">
                {job.count.toLocaleString()}
              </span>
              <span className="min-w-0 flex-1 text-sm text-muted-foreground">
                {job.label}
              </span>
              <span
                aria-hidden="true"
                className="rounded-full border border-border px-2.5 py-1 text-xs font-medium"
              >
                {job.action}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </HomeModule>
  );
}
