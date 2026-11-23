import { useState } from "react";

import type { ItemType } from "@/api/library";
import { cn } from "@/lib/utils";

import { MoreLikeThisSheet, type Seed } from "./MoreLikeThisSheet";
import { recommendationFor } from "./recommendation";

/**
 * The *More like this* button and the sheet it opens (Sprint 134). Drawn only for
 * a library the server says has a source; when that source is not configured the
 * sheet says how to configure it and asks nothing.
 */
export function MoreLikeThis({
  seed,
  types,
  className,
  children = "More like this",
}: {
  seed: Seed;
  types: ItemType[] | undefined;
  className?: string;
  children?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  if (!recommendationFor(seed.type, types)) return null;
  return (
    <>
      <button
        type="button"
        className={cn(className)}
        aria-label={`More like ${seed.title}`}
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        {children}
      </button>
      <MoreLikeThisSheet
        seed={seed}
        open={open}
        onOpenChange={setOpen}
        types={types}
      />
    </>
  );
}
