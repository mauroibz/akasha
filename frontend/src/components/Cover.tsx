import type { ReactNode } from "react";

import { CoverImage } from "@/components/CoverImage";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

export type CoverSize = "s" | "m" | "l";

/** The book-shaped corner and the spine's shade, by size. A thumbnail casts no shadow. */
const shapes: Record<CoverSize, string> = {
  s: "rounded-[2px_4px_4px_2px]",
  m: "rounded-[3px_7px_7px_3px] shadow-[inset_4px_0_0_rgba(0,0,0,0.15),0_12px_22px_-12px_rgba(28,25,23,0.45)]",
  l: "rounded-[3px_7px_7px_3px] shadow-[inset_5px_0_0_rgba(0,0,0,0.18),0_16px_26px_-14px_rgba(28,25,23,0.5)]",
};

export interface CoverProps {
  src: string | null | undefined;
  /** `s` in a row of text, `m` in a grid, `l` where the covers are the screen. */
  size: CoverSize;
  /** Names the image when nothing beside it does; empty beside a caption or a named link. */
  alt?: string;
  title?: string;
  creator?: string | null;
  score?: number | null;
  /** Drawn in place of the stock placeholder when there is no cover. */
  fallback?: ReactNode;
  className?: string;
}

/**
 * One cover (Sprint 139, DEC-193): the shape, the corner and the shadow every list
 * of covers shares, at three sizes, with one caption. It takes its container's
 * width. Built from spans so it can sit inside a link or a button; inside a `group`
 * it lifts on hover.
 */
export function Cover({
  src,
  size,
  alt = "",
  title,
  creator,
  score,
  fallback,
  className,
}: CoverProps) {
  return (
    <span data-size={size} className={cn("block min-w-0", className)}>
      <span
        className={cn(
          "block aspect-[2/3] overflow-hidden",
          shapes[size],
          size !== "s" &&
            "transition-transform duration-300 group-hover:-translate-y-1 motion-reduce:transform-none",
        )}
      >
        {!src && fallback ? (
          fallback
        ) : (
          <CoverImage
            src={src}
            alt={alt}
            className="h-full w-full object-cover"
            placeholderClassName="h-full w-full"
          />
        )}
      </span>
      {title !== undefined && (
        <span
          className={cn(
            "block font-display leading-tight",
            size === "l" ? "mt-3 text-lg" : "mt-2 text-base",
            "line-clamp-2",
          )}
        >
          {title}
        </span>
      )}
      {title !== undefined &&
        (creator || (score !== null && score !== undefined)) && (
          <span className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <span className="truncate">{creator}</span>
            {score !== null && score !== undefined && (
              <span
                className={cn(scoreChipShape, "ml-auto", scoreChipClass(score))}
              >
                {score}
              </span>
            )}
          </span>
        )}
    </span>
  );
}
