import { Link } from "react-router-dom";

import type { HomeCover, HomeLibraryYear, ModuleSize } from "@/api/home";
import type { ItemType } from "@/api/library";
import {
  slotsInOrder,
  yearPassed,
  type SlotCover,
} from "@/features/goals/goals";
import { Bar, Slots } from "@/features/goals/GoalBand";

import { HomeModule } from "./HomeModule";

/** Columns of covers by size: the goal band's six at M, fewer small, more large. */
const columns: Record<ModuleSize, string> = {
  S: "grid w-full grid-cols-4 gap-2",
  M: "grid w-full grid-cols-6 gap-2",
  L: "grid w-full grid-cols-8 gap-2",
};
/** Covers shown without a goal's slots: two rows at each size, three large. */
const SHOWN: Record<ModuleSize, number> = { S: 8, M: 12, L: 24 };

function coverOf(cover: HomeCover): SlotCover {
  return { id: cover.entry_id, title: cover.title, cover_url: cover.cover_url };
}

/**
 * One library's year on Home (Sprint 138, DEC-192): the Diary goal band's grid. With a
 * goal of 24 or fewer, a slot per thing aimed at, the year's covers in finishing order
 * and a dashed slot for each still to come; above 24, the band's bar and the covers;
 * without a goal, the covers alone. Opens the Diary.
 */
export function LibraryYear({
  year,
  types,
  size = "M",
  today = new Date(),
  className,
}: {
  year: HomeLibraryYear;
  types: ItemType[] | undefined;
  size?: ModuleSize;
  today?: Date;
  className?: string;
}) {
  const declared = (Array.isArray(types) ? types : []).find(
    (type) => type.id === year.item_type,
  );
  const plural = (declared?.plural_label ?? "items").toLowerCase();
  const covers = year.covers.map(coverOf);
  const target = year.goal?.target ?? null;
  const slots = target === null ? null : slotsInOrder(target, covers);
  const loose = slots
    ? null
    : covers.slice(0, SHOWN[size]).map((entry) => ({ entry, next: false }));
  const more = year.total - (slots ? covers.length : (loose?.length ?? 0));
  const label =
    target === null
      ? `${year.total} ${plural} in ${year.year}`
      : `${year.total} of ${target} ${plural} in ${year.year}`;
  return (
    <HomeModuleFrame
      title={`Your ${year.year} ${plural}`}
      className={className}
    >
      <p className="mb-3 flex flex-wrap items-baseline gap-x-2">
        <span className="font-display text-3xl tabular-nums text-primary">
          {year.total}
        </span>
        <span className="text-sm text-muted-foreground">
          {target === null ? `finished in ${year.year}` : `of ${target}`}
        </span>
      </p>
      {slots ? (
        <Slots slots={slots} label={label} className={columns[size]} />
      ) : (
        <>
          {target !== null ? (
            <Bar
              total={year.total}
              target={target}
              passed={yearPassed(year.year, today)}
              label={label}
              className="mb-3 w-full"
            />
          ) : null}
          <Slots slots={loose ?? []} label={label} className={columns[size]} />
          {more > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              and {more} more
            </p>
          ) : null}
        </>
      )}
    </HomeModuleFrame>
  );
}

function HomeModuleFrame({
  title,
  className,
  children,
}: {
  title: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <HomeModule
      title={title}
      className={className}
      aside={
        <Link
          to="/diary"
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          Diary →
        </Link>
      }
    >
      {children}
    </HomeModule>
  );
}
