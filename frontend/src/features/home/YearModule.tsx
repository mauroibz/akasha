import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { HomeYear } from "@/api/home";
import type { ItemType } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { cn } from "@/lib/utils";

import { HomeModule } from "./HomeModule";
import { fitMonths, leadGoal, yearCells } from "./year";

const initials = Array.from({ length: 12 }, (_, month) =>
  new Intl.DateTimeFormat("en", { month: "narrow" }).format(
    new Date(2026, month, 1),
  ),
);
const names = Array.from({ length: 12 }, (_, month) =>
  new Intl.DateTimeFormat("en", { month: "long" }).format(
    new Date(2026, month, 1),
  ),
);

/**
 * The year (Sprint 130): twelve months, the year's covers in each, and from this
 * month on an empty slot for each thing the lead goal still needs. Other libraries'
 * finishes that month are a count beside them. Each cover opens its entry. The strip
 * takes whatever height its row gives it, and the covers grow to fill it (Sprint 132).
 */
export function YearModule({
  year,
  types,
  today = new Date(),
  className,
}: {
  year: HomeYear;
  types: ItemType[] | undefined;
  today?: Date;
  className?: string;
}) {
  const goal = leadGoal(year);
  const cells = yearCells(year, today);
  const finished = year.months.reduce((sum, month) => sum + month.count, 0);
  const declared = (Array.isArray(types) ? types : []).find(
    (type) => type.id === goal?.item_type,
  );
  const plural = (declared?.plural_label ?? "items").toLowerCase();
  const area = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const element = area.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const measure = () =>
      setBox({ width: element.clientWidth, height: element.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const most = Math.max(
    0,
    ...cells.map((cell) => cell.covers.length + cell.empty),
  );
  const fit = fitMonths(box, Math.max(1, most));
  return (
    <HomeModule
      title={String(year.year)}
      className={cn("flex flex-col", className)}
      aside={
        <Link
          to="/diary"
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          Diary →
        </Link>
      }
    >
      {goal ? (
        <p className="mb-3 flex flex-wrap items-baseline gap-x-3">
          <span className="font-display text-3xl tabular-nums text-primary">
            {goal.done} / {goal.target}
          </span>
          <span className="text-sm text-muted-foreground">
            {plural} · {goal.count} a {goal.period}
          </span>
        </p>
      ) : finished === 0 ? (
        <p className="mb-3 text-sm text-muted-foreground">
          Nothing finished yet in {year.year}.
        </p>
      ) : (
        <p className="mb-3 text-sm text-muted-foreground">
          <span className="font-display text-3xl tabular-nums text-primary">
            {finished}
          </span>{" "}
          finished in {year.year}
        </p>
      )}
      <div
        className={cn(
          "relative",
          // An empty year keeps to a strip of month letters; a year with covers fills.
          most > 0 ? "min-h-36 flex-1" : "min-h-12",
        )}
      >
        <ol className="absolute inset-0 grid min-w-0 grid-cols-12 gap-1">
          {cells.map((cell) => {
            const shown = cell.covers.slice(0, fit.cells);
            const more = cell.covers.length - shown.length;
            const room = Math.max(
              0,
              Math.min(cell.empty, fit.cells - shown.length),
            );
            return (
              <li
                key={cell.month}
                aria-label={`${names[cell.month - 1]}: ${cell.covers.length + cell.others} finished`}
                aria-current={cell.current ? "date" : undefined}
                className="flex min-h-0 min-w-0 flex-col items-stretch gap-1"
              >
                <div
                  ref={cell.month === 1 ? area : undefined}
                  className="grid min-h-0 flex-1 content-end gap-1 overflow-hidden"
                  style={{
                    gridTemplateColumns: `repeat(${fit.columns}, minmax(0, 1fr))`,
                  }}
                >
                  {shown.map((cover) => (
                    <Link
                      key={cover.entry_id}
                      to={`/books/${cover.entry_id}`}
                      aria-label={cover.title}
                      title={cover.title}
                      className="block rounded-sm focus-ring"
                    >
                      <CoverImage
                        src={cover.cover_url}
                        alt=""
                        className="aspect-[2/3] w-full rounded-sm object-cover"
                        placeholderClassName="aspect-[2/3] w-full rounded-sm [&_svg]:hidden"
                      />
                    </Link>
                  ))}
                  {Array.from({ length: room }, (_, index) => (
                    <span
                      key={`room-${index}`}
                      aria-hidden="true"
                      className="block aspect-[2/3] w-full rounded-sm border border-dashed border-primary/50"
                    />
                  ))}
                </div>
                <span
                  className={cn(
                    "text-center text-[10px] tabular-nums text-muted-foreground",
                    cell.current && "font-semibold text-primary",
                  )}
                  aria-hidden="true"
                >
                  {initials[cell.month - 1]}
                </span>
                {/* Always drawn, so every month's letter sits on one line. */}
                <span
                  className="h-3 text-center text-[10px] leading-3 tabular-nums text-muted-foreground"
                  aria-hidden="true"
                >
                  {more + cell.others > 0 ? `+${more + cell.others}` : ""}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
      {goal &&
      year.months.some((m) => m.count > (m.counts[goal.item_type] ?? 0)) ? (
        <p className="mt-2 text-xs text-muted-foreground">
          + counts what other libraries finished that month.
        </p>
      ) : null}
    </HomeModule>
  );
}
