import { Link } from "react-router-dom";

import type { ChronologyBucket } from "@/features/library/insights";
import { scoreBand, scoreFillClass } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * Decades drawn as a timeline, not ranked by count (Sprint 073 deliverable 3,
 * finding 10): ascending time order, bar height by how many, fill by the band
 * the decade's mean score belongs to — a decade nobody rated draws as the
 * neutral surface rather than a ramp colour, since there is no mean to band.
 * An empty decade is kept as a zero-height gap: skipping it would say the
 * decade does not exist, when it says only that this library holds nothing
 * from it.
 */
export function ChronologyStrip({
  buckets,
  hrefFor,
}: {
  buckets: ChronologyBucket[];
  hrefFor: (bucket: ChronologyBucket) => string;
}) {
  const max = Math.max(...buckets.map((bucket) => bucket.count), 1);

  return (
    <ul
      aria-label="Decades, in chronological order"
      className="flex h-32 items-end gap-2 px-4"
    >
      {buckets.map((bucket) => {
        const height =
          bucket.count === 0 ? 0 : Math.max((bucket.count / max) * 100, 6);
        return (
          <li
            key={bucket.decade}
            className="flex h-full flex-1 flex-col items-center justify-end gap-1"
          >
            {bucket.count > 0 ? (
              <Link
                to={hrefFor(bucket)}
                aria-label={`${bucket.label}: ${bucket.count} ${
                  bucket.count === 1 ? "entry" : "entries"
                }${
                  bucket.meanScore !== null
                    ? `, mean score ${bucket.meanScore.toFixed(1)}`
                    : ", none rated"
                }`}
                className="flex h-full w-full min-h-11 flex-col items-center justify-end gap-1 rounded-sm focus-ring"
              >
                <span
                  aria-hidden="true"
                  data-chronology-bucket={bucket.decade}
                  data-count={bucket.count}
                  style={{ height: `${height}%` }}
                  className={cn(
                    "w-full min-h-[2px] rounded-t-sm",
                    bucket.meanScore !== null
                      ? scoreFillClass[scoreBand(Math.round(bucket.meanScore))]
                      : "bg-muted",
                  )}
                />
              </Link>
            ) : (
              <span
                aria-hidden="true"
                data-chronology-bucket={bucket.decade}
                data-count={0}
                className="h-[2px] w-full rounded-t-sm bg-border"
              />
            )}
            <span className="text-[10px] tabular-nums text-muted-foreground">
              {bucket.label}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
