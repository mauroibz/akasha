import { Link } from "react-router-dom";

import type { HomeDomainTile } from "@/api/home";
import type { ItemType, StatusSpec } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { statusesFor } from "@/features/library/labels";
import { cn } from "@/lib/utils";

import { HomeModule } from "./HomeModule";

/** A status's colour on the bar comes from what the domain declares it to be. */
function segmentClass(status: StatusSpec | undefined): string {
  if (status?.finished) return "bg-primary";
  if (status?.in_progress) return "bg-score-top";
  if (status?.abandoned) return "bg-score-low";
  if (status?.planned) return "bg-muted-foreground/50";
  return "bg-foreground/30";
}

function Tile({
  tile,
  types,
}: {
  tile: HomeDomainTile;
  types: ItemType[] | undefined;
}) {
  const declared = (Array.isArray(types) ? types : []).find(
    (type) => type.id === tile.item_type,
  );
  const plural = declared?.plural_label ?? "Items";
  const statuses = statusesFor(tile.item_type, types);
  const rows = Object.entries(tile.status_counts).map(([value, count]) => {
    const spec = statuses.find((status) => status.value === value);
    return { value, count, spec, label: (spec?.label ?? value).toLowerCase() };
  });
  const tallest = Math.max(1, ...tile.scores);
  const slots = Array.from({ length: 3 }, (_, index) => tile.covers[index]);
  return (
    <Link
      to={`/library?type=${encodeURIComponent(tile.item_type)}`}
      aria-label={`${tile.count.toLocaleString()} ${plural}, open the library`}
      className="flex min-w-0 flex-col gap-3 rounded-xl border border-border bg-surface p-3 transition-colors hover:border-primary/50 focus-ring"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-display text-2xl tabular-nums">
          {tile.count.toLocaleString()}
        </span>
        <span className="truncate text-xs text-muted-foreground">{plural}</span>
      </div>
      <div className="grid grid-cols-3 gap-1">
        {slots.map((cover, index) =>
          cover ? (
            <CoverImage
              key={cover.entry_id}
              src={cover.cover_url}
              alt=""
              className="aspect-[2/3] w-full rounded-sm object-cover"
              placeholderClassName="aspect-[2/3] w-full rounded-sm [&_svg]:hidden"
            />
          ) : (
            <span
              key={`empty-${index}`}
              aria-hidden="true"
              className="aspect-[2/3] w-full rounded-sm border border-dashed border-border"
            />
          ),
        )}
      </div>
      <div
        className="flex h-1.5 overflow-hidden rounded-full bg-muted"
        aria-hidden="true"
      >
        {rows.map((row) => (
          <span
            key={row.value}
            className={segmentClass(row.spec)}
            style={{ width: `${(row.count / Math.max(1, tile.count)) * 100}%` }}
          />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
        {rows.map((row) => (
          <li key={row.value}>
            {row.count.toLocaleString()} {row.label}
          </li>
        ))}
      </ul>
      <div className="flex h-8 items-end gap-0.5" aria-hidden="true">
        {tile.scores.map((count, index) => (
          <span
            key={index}
            className={cn(
              "flex-1 rounded-t-sm",
              count ? "bg-muted-foreground/60" : "bg-border",
            )}
            style={{ height: `${Math.max(8, (count / tallest) * 100)}%` }}
          />
        ))}
      </div>
      <div className="flex flex-wrap justify-between gap-x-2 text-xs text-muted-foreground">
        <span>
          {tile.mean_score === null
            ? "no scores"
            : `avg ${tile.mean_score.toFixed(1)}`}
        </span>
        {tile.without_cover ? (
          <span>{tile.without_cover.toLocaleString()} without a cover</span>
        ) : null}
      </div>
    </Link>
  );
}

/**
 * The whole library at a glance (Sprint 130): one tile per registered domain that
 * holds entries, read from the payload rather than named here, so a domain added
 * later has a tile without this file changing. Each opens `/library?type=…`.
 */
export function LibraryTiles({
  tiles,
  types,
  className,
}: {
  tiles: HomeDomainTile[];
  types: ItemType[] | undefined;
  className?: string;
}) {
  return (
    <HomeModule title="Your libraries" className={className}>
      <div className="grid grid-cols-2 gap-3 min-[720px]:grid-cols-3 lg:grid-cols-5">
        {tiles.map((tile) => (
          <Tile key={tile.item_type} tile={tile} types={types} />
        ))}
      </div>
    </HomeModule>
  );
}
