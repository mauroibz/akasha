import { Link } from "react-router-dom";

import { CoverImage } from "@/components/CoverImage";
import {
  memberPreview,
  useInsightMembers,
} from "@/features/library/useInsightMembers";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * What is behind one ranking row, opened in place (Sprint 066).
 *
 * The link into the filtered library stays — it is how you act on these entries
 * rather than just look at them — but it is now the end of a panel instead of the
 * only thing a row could do.
 */
export function InsightsMembers({
  id,
  type,
  insightKey,
  value,
  count,
  href,
}: {
  id: string;
  type: string;
  insightKey: string;
  value: string;
  count: number;
  href: string;
}) {
  const members = useInsightMembers({
    type,
    insightKey,
    value,
    enabled: true,
  });

  return (
    <div id={id} className="ml-3 mt-1 border-l-2 border-primary/40 pl-3 pr-1">
      {members.isPending && (
        <p role="status" className="py-2 text-xs text-muted-foreground">
          Opening…
        </p>
      )}
      {members.isError && (
        <p role="alert" className="py-2 text-xs text-destructive">
          These could not be loaded
        </p>
      )}

      <ul className="flex flex-col">
        {members.data?.items.map((entry) => (
          <li key={entry.id} className="flex items-center gap-3 py-1">
            <CoverImage
              src={entry.item.cover_url}
              alt=""
              className="h-9 w-7 shrink-0 object-cover"
              placeholderClassName="h-9 w-7 shrink-0 [&_svg]:h-4 [&_svg]:w-4"
            />
            <span className="min-w-0 flex-1 truncate text-xs">
              {entry.item.title}
            </span>
            {entry.item.year !== null && (
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {entry.item.year}
              </span>
            )}
            <span
              className={cn(
                "shrink-0 text-xs",
                scoreChipShape,
                scoreChipClass(entry.score),
              )}
            >
              {entry.score ?? "—"}
            </span>
          </li>
        ))}
      </ul>

      {count > memberPreview && (
        <p className="pt-0.5 text-xs text-muted-foreground">
          and {count - memberPreview} more
        </p>
      )}

      <Link
        to={href}
        className="mb-2 mt-1.5 inline-flex min-h-11 items-center text-xs font-medium text-primary hover:underline focus-ring"
      >
        Open all {count} in the library →
      </Link>
    </div>
  );
}
