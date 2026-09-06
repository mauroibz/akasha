import { Link } from "react-router-dom";

import type { ItemType } from "@/api/library";
import type { ShelfWithCount } from "@/api/shelves";
import { CoverImage } from "@/components/CoverImage";
import { ShelfRail } from "@/features/shelves/ShelfRail";
import { magnitude, weightClass } from "@/features/library/insights";

/**
 * One shelf, drawn as a shelf (Sprint 074 deliverable 2, finding 14) — a board
 * card instead of a 90px row. The whole card is one link into `/shelves/:slug`;
 * `ShelfRail` inside it holds no focusable content of its own (AC2), so a
 * keyboard or screen reader user reaches exactly one stop per shelf.
 */
export function ShelfCard({
  shelf,
  max,
  domains,
  /** When set, chips and the magnitude bar count only this domain's members
   * (deliverable 3) — the card's own link still opens the shelf whole. */
  domainFilter,
}: {
  shelf: ShelfWithCount;
  max: number;
  domains: readonly ItemType[];
  domainFilter?: string;
}) {
  const membersByType = shelf.members_by_type ?? {};
  const shownCount = domainFilter
    ? (membersByType[domainFilter] ?? 0)
    : shelf.entry_count;
  const covers = shelf.covers ?? [];

  return (
    <Link
      to={`/shelves/${encodeURIComponent(shelf.slug)}`}
      className="focus-ring flex flex-col overflow-hidden rounded-xl border border-border bg-surface hover:border-muted-foreground"
      data-shelf-card=""
    >
      <div className="pt-3.5">
        {shelf.entry_count === 0 ? null : covers.length > 0 ? (
          <ShelfRail covers={covers} />
        ) : (
          <div className="px-3 pb-2.5">
            <CoverImage src={null} alt="" className="h-[74px] w-[50px]" />
          </div>
        )}
      </div>

      <div className="relative flex flex-col gap-2 px-4 pb-4 pt-1">
        <span
          aria-hidden="true"
          data-magnitude={String(magnitude(shownCount, max))}
          style={{
            width: `${Number((magnitude(shownCount, max) * 100).toFixed(1))}%`,
          }}
          className="absolute inset-x-0 top-0 h-0.5 rounded-full bg-primary/40"
        />
        <div className="flex items-baseline justify-between gap-3">
          <p data-shelf-name="" className="truncate font-semibold">
            {shelf.name}
          </p>
          <p
            className={
              shownCount === 0
                ? "shrink-0 text-sm text-muted-foreground"
                : `shrink-0 ${weightClass(shownCount, max)}`
            }
          >
            {shownCount === 0
              ? "Empty"
              : `${shownCount} ${shownCount === 1 ? "item" : "items"}`}
          </p>
        </div>
        {Object.keys(membersByType).length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {Object.entries(membersByType).map(([type, count]) => (
              <li
                key={type}
                className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground"
              >
                {`${domains.find((domain) => domain.id === type)?.label ?? type} ${count}`}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Link>
  );
}
