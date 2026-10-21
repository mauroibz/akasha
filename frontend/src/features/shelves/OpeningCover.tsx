import { Link } from "react-router-dom";

import { CoverImage } from "@/components/CoverImage";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * A cover standing on a shelf that opens when you reach for it (Sprint 105,
 * DEC-169: "a hover on a shelf should open the cover as an animation").
 *
 * The front cover turns back on its spine, about 0.4s, past upright, the way a
 * book lies open, so the whole inside page shows: the title, year and score. Keyboard focus opens it too. It stays shut where
 * motion is unwelcome (`prefers-reduced-motion`) and where there is no hover
 * (a touch screen), and it is always a link to the entry either way.
 */
export function OpeningCover({
  href,
  title,
  year,
  score,
  coverUrl,
  seed,
  className,
  tilt,
}: {
  href: string;
  title: string;
  year: number | null;
  score: number | null;
  coverUrl: string | null;
  /** Picks a typeset cover's colour, stable per entry. */
  seed: number;
  /** Width and height of the cover. */
  className: string;
  /** A slight lean, for a shelf that is not a parade. */
  tilt?: boolean;
}) {
  const label = [title, year, score !== null ? `scored ${score}` : null]
    .filter(Boolean)
    .join(", ");
  return (
    <Link
      to={href}
      aria-label={label}
      data-opening-cover=""
      className={cn(
        "group/cover relative block shrink-0 rounded-[2px_6px_6px_2px] [perspective:900px] hover:z-10 focus-visible:z-10 focus-visible:outline-none",
        tilt && "-rotate-3 origin-bottom",
        className,
      )}
    >
      {/* The inside page: what the opened cover reveals. */}
      <span
        aria-hidden="true"
        className="absolute inset-0 flex flex-col justify-between rounded-[2px_6px_6px_2px] bg-surface-raised p-3 ring-1 ring-border group-focus-visible/cover:ring-2 group-focus-visible/cover:ring-primary"
      >
        <span className="line-clamp-4 font-display text-[15px] leading-tight text-foreground">
          {title}
        </span>
        <span className="flex items-end justify-between gap-2 text-xs text-muted-foreground">
          <span className="tabular-nums">{year ?? ""}</span>
          {score !== null && (
            <span className={cn(scoreChipShape, scoreChipClass(score))}>
              {score}
            </span>
          )}
        </span>
      </span>
      {/* The front cover, hinged on its spine. */}
      <span
        aria-hidden="true"
        data-cover-front=""
        className={cn(
          "absolute inset-0 origin-left rounded-[2px_6px_6px_2px] [transform-style:preserve-3d]",
          "transition-transform duration-[400ms] ease-[cubic-bezier(0.2,0.7,0.2,1)]",
          "[@media(hover:hover)_and_(prefers-reduced-motion:no-preference)]:group-hover/cover:[transform:rotateY(-115deg)]",
          "motion-safe:group-focus-visible/cover:[transform:rotateY(-115deg)]",
          "shadow-[inset_5px_0_0_rgba(0,0,0,0.18),0_14px_22px_-12px_rgba(28,25,23,0.55)]",
        )}
      >
        <span className="absolute inset-0 overflow-hidden rounded-[2px_6px_6px_2px] [backface-visibility:hidden]">
          {coverUrl ? (
            <CoverImage
              src={coverUrl}
              alt=""
              className="h-full w-full object-cover"
              placeholderClassName="h-full w-full"
            />
          ) : (
            <TypesetCover title={title} seed={seed} />
          )}
        </span>
        {/* The cover's inner side, seen once it has turned. */}
        <span className="absolute inset-0 rounded-[2px_6px_6px_2px] bg-muted [backface-visibility:hidden] [transform:rotateY(180deg)]" />
      </span>
    </Link>
  );
}

const covers = [
  "#2F4A5C",
  "#8C3B2E",
  "#7D6431",
  "#3E5E3A",
  "#6B4E7A",
  "#1F2A36",
  "#A3542A",
  "#4F6D7A",
  "#7A2E3B",
];

/** A cover drawn from the title, for an item with no art of its own. */
export function TypesetCover({ title, seed }: { title: string; seed: number }) {
  return (
    <span
      style={{ backgroundColor: covers[Math.abs(seed) % covers.length] }}
      className="flex h-full w-full items-end p-3"
    >
      <span className="line-clamp-5 font-display text-[15px] leading-tight text-[#FBF8F1]">
        {title}
      </span>
    </span>
  );
}
