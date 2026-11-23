import { Link } from "react-router-dom";

import type { HomeShelf, ModuleSize } from "@/api/home";

import { HomeModule } from "./HomeModule";

const SHOWN: Record<ModuleSize, number> = { S: 4, M: 6, L: 8 };

/**
 * Shelves in use (Sprint 131): the shelves whose members were touched last, each
 * with its count, opening the shelf. Hidden when no shelf holds anything.
 */
export function ShelvesModule({
  shelves,
  size,
  className,
}: {
  shelves: HomeShelf[];
  size: ModuleSize;
  className?: string;
}) {
  return (
    <HomeModule
      title="Shelves"
      className={className}
      aside={
        <Link
          to="/shelves"
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          All shelves →
        </Link>
      }
    >
      <ul className="flex flex-wrap gap-2">
        {shelves.slice(0, SHOWN[size]).map((shelf) => (
          <li key={shelf.id} className="min-w-0">
            <Link
              to={`/shelves/${encodeURIComponent(shelf.slug)}`}
              aria-label={`${shelf.name}, ${shelf.entry_count}`}
              className="inline-flex min-h-9 max-w-full items-center gap-1.5 rounded-full border border-border px-3 text-sm transition-colors hover:bg-accent focus-ring"
            >
              <span className="truncate">{shelf.name}</span>
              <span className="text-xs tabular-nums text-muted-foreground">
                {shelf.entry_count}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </HomeModule>
  );
}
