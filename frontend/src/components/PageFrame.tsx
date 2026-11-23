import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * A page's width (Sprint 139, DEC-193). `wide` is for a screen of covers, `reading`
 * for text and forms, `focus` for a screen that holds one thing at a time: a game's
 * card, a page that was not found.
 */
export type PageWidth = "wide" | "reading" | "focus";

const widths: Record<PageWidth, string> = {
  wide: "max-w-[1440px]",
  reading: "max-w-[960px]",
  focus: "max-w-xl",
};

/**
 * The one `<main>` (Sprint 139): the landmark, its width and its side padding, so
 * no page writes its own. A page passes only the spacing that is its own, such as
 * room at the foot for a fixed bar.
 */
export function PageFrame({
  width,
  className,
  children,
  ...rest
}: { width: PageWidth } & ComponentProps<"main">) {
  return (
    <main
      {...rest}
      data-width={width}
      className={cn(
        "mx-auto min-h-screen w-full px-5 py-8 sm:px-8",
        widths[width],
        className,
      )}
    >
      {children}
    </main>
  );
}
