import { Link } from "react-router-dom";

import type { HomeTidy } from "@/api/home";
import type { ItemType } from "@/api/library";
import { countLabel } from "@/features/library/labels";

import { HomeModule } from "./HomeModule";

/**
 * One library's finished entries with no score. The library opens one domain at a
 * time, so each domain gets its own link and the count it shows is the one here.
 */
function unscoredHref(itemType: string, types: ItemType[] | undefined) {
  const params = new URLSearchParams({ type: itemType });
  const declared = (Array.isArray(types) ? types : []).find(
    (type) => type.id === itemType,
  );
  for (const status of declared?.statuses ?? [])
    if (status.finished) params.append("status", status.value);
  params.set("unscored", "true");
  return `/library?${params.toString()}`;
}

/**
 * Small jobs (Sprint 131): pairs that look like one work, what has no cover, what
 * was finished without a score. Each count opens what resolves it: the duplicates
 * and covers decks, and the library filtered to the unscored, one link per library
 * since the library shows one at a time. A count of nothing is left out; the module
 * is hidden when every count is.
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
  const unscored = Object.entries(tidy.unscored_by_type ?? {});
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
  ];
  if (unscored.length === 1)
    jobs.push({
      count: tidy.unscored,
      label: "finished, not scored",
      action: "Score",
      to: unscoredHref(unscored[0][0], types),
    });
  const shown = jobs.filter((job) => job.count > 0);
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
        {shown.map((job) => (
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
        {unscored.length > 1 ? (
          <li className="py-1.5">
            <p className="flex items-center gap-3">
              <span className="font-display text-2xl tabular-nums">
                {tidy.unscored.toLocaleString()}
              </span>
              <span className="text-sm text-muted-foreground">
                finished, not scored
              </span>
            </p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {unscored.map(([itemType, count]) => (
                <li key={itemType}>
                  <Link
                    to={unscoredHref(itemType, types)}
                    className="inline-flex min-h-9 items-center rounded-full border border-border px-2.5 text-xs font-medium transition-colors hover:bg-accent focus-ring"
                  >
                    {countLabel(count, itemType, types)}
                  </Link>
                </li>
              ))}
            </ul>
          </li>
        ) : null}
      </ul>
    </HomeModule>
  );
}
