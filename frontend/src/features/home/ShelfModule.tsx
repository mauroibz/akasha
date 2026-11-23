import { Link } from "react-router-dom";

import type { HomeShelfModule, ModuleSize } from "@/api/home";
import { Slots } from "@/features/goals/GoalBand";

import { HomeModule } from "./HomeModule";

const columns: Record<ModuleSize, string> = {
  S: "grid w-full grid-cols-4 gap-2",
  M: "grid w-full grid-cols-6 gap-2",
  L: "grid w-full grid-cols-8 gap-2",
};
/** Two rows at each size, three large. */
const SHOWN: Record<ModuleSize, number> = { S: 8, M: 12, L: 24 };

/**
 * A shelf placed on Home (Sprint 138, DEC-192): its name, how many it holds and the
 * covers of what changed last, each opening its entry; the heading's link opens the
 * shelf. Turned on per shelf in *Edit home*.
 */
export function ShelfModule({
  shelf,
  size = "M",
  className,
}: {
  shelf: HomeShelfModule;
  size?: ModuleSize;
  className?: string;
}) {
  const shown = shelf.covers.slice(0, SHOWN[size]);
  return (
    <HomeModule
      title={shelf.name}
      className={className}
      aside={
        <Link
          to={`/shelves/${encodeURIComponent(shelf.slug)}`}
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          {shelf.entry_count.toLocaleString()} on the shelf →
        </Link>
      }
    >
      {shown.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing on it yet.</p>
      ) : (
        <Slots
          slots={shown.map((cover) => ({
            entry: {
              id: cover.entry_id,
              title: cover.title,
              cover_url: cover.cover_url,
            },
            next: false,
          }))}
          label={`${shelf.name}, ${shelf.entry_count}`}
          className={columns[size]}
        />
      )}
    </HomeModule>
  );
}
