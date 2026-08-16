import { m } from "motion/react";

import type { SearchCandidate } from "@/api/add";
import { CoverImage } from "@/components/CoverImage";
import { useMotionPresets } from "@/lib/motion";

export interface ResultsGridProps {
  results: SearchCandidate[];
  onSelect: (candidate: SearchCandidate) => void;
  /** Where *None of these* goes. The host owns it: on `/` it leaves for `/add`. */
  onManual: () => void;
  label: string;
}

/**
 * Provider results, as cards, with the manual escape hatch at the end of the list.
 *
 * Shared because Sprint 029 moved this list from `/add` onto `/` without redesigning
 * it, and the staggered entry is part of what was walked through in Sprint 027.
 */
export function ResultsGrid(props: ResultsGridProps) {
  const presets = useMotionPresets();
  // Identity of the committed result set, so a new search re-staggers and a
  // re-render of the same results does not.
  const resultsKey = props.results.map((row) => row.source_id).join("|");
  return (
    // Results arrive in sequence rather than all at once. The delay stops growing
    // after a handful of cards: a twenty-result search would otherwise take most of
    // a second to finish arriving, which reads as slow rather than as considered.
    <m.section
      aria-label={props.label}
      className="mt-6 grid gap-3 sm:grid-cols-2"
      key={resultsKey}
      initial="hidden"
      animate="show"
    >
      {props.results.map((row, index) => (
        <m.button
          key={`${row.source}:${row.source_id}`}
          type="button"
          variants={presets.staggerItem(index)}
          className="min-h-28 rounded-2xl bg-surface p-4 text-left focus-ring"
          onClick={() => props.onSelect(row)}
        >
          <span className="grid grid-cols-[64px_1fr] gap-3">
            <CoverImage
              src={row.cover_url}
              alt={`Cover of ${row.title}`}
              className="aspect-[2/3] w-16"
            />
            <span>
              <strong>{row.title}</strong>
              <span className="mt-1 block text-muted-foreground">
                {row.credit ?? (row.creators.join(", ") || "Unknown creator")}
              </span>
              <span className="block text-sm">
                Edition year: {row.year ?? "unknown"}
                {row.metadata?.publisher ? ` · ${row.metadata.publisher}` : ""}
                {row.language ? ` · ${row.language}` : ""}
              </span>
              {row.original_year && row.original_year !== row.year && (
                <span className="block text-sm">
                  Originally published: {row.original_year}
                </span>
              )}
              <span className="text-xs uppercase text-primary">
                {row.source}
              </span>
            </span>
          </span>
        </m.button>
      ))}
      {/* Part of the same list, and the option a reader reaches for last, so it
          arrives last rather than ahead of the results it follows. */}
      <m.button
        type="button"
        variants={presets.staggerItem(props.results.length)}
        className="min-h-28 rounded-2xl border border-dashed border-border p-4 text-left focus-ring"
        onClick={props.onManual}
      >
        None of these — enter manually
      </m.button>
    </m.section>
  );
}
