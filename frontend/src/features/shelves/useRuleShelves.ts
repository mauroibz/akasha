import { useQueries, useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/api/keys";
import { getLibraryPage } from "@/api/library";
import type { ShelfWithCount } from "@/api/shelves";
import { getViews, type SavedView } from "@/api/views";
import { filtersFromParams } from "@/features/library/library";

/** How many shelves with a rule are drawn; each is one list request for its covers. */
export const RULE_SHELVES = 12;
const PREVIEW = 8;

export interface RuleShelf {
  view: SavedView;
  /** The same shape a hand-picked shelf has, so one row draws both. */
  shelf: ShelfWithCount;
  /** The Library filtered as the rule says. */
  href: string;
}

/**
 * Shelves that follow a rule (Sprint 145, DEC-193): a saved view (Sprint 100) drawn
 * as a shelf. A view is the Library's address under a name, so what is on the shelf
 * is whatever the Library lists at that address now: a count and the first covers,
 * one bounded request each, from stored data. Nothing is copied onto the shelf, so
 * an entry joins or leaves it by coming to match or not.
 */
export function useRuleShelves(): RuleShelf[] {
  const views = useQuery({
    queryKey: queryKeys.views,
    queryFn: ({ signal }) => getViews(signal),
    retry: false,
  });
  const rows = (Array.isArray(views.data) ? views.data : []).slice(
    0,
    RULE_SHELVES,
  );
  const pages = useQueries({
    queries: rows.map((view) => ({
      queryKey: [...queryKeys.views, "shelf", view.id, view.query],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        getLibraryPage(
          filtersFromParams(new URLSearchParams(view.query)),
          undefined,
          signal,
          PREVIEW,
        ),
      retry: false,
      staleTime: 30_000,
    })),
  });
  return rows.map((view, index) => {
    const page = pages[index]?.data;
    const items = Array.isArray(page?.items) ? page.items : [];
    return {
      view,
      href: `/?${view.query}`,
      shelf: {
        id: -view.id,
        name: view.name,
        slug: `rule-${view.id}`,
        entry_count: page?.total ?? items.length,
        preview: items.map((entry) => ({
          entry_id: entry.id,
          title: entry.item.title,
          year: entry.item.year ?? null,
          score: entry.score ?? null,
          cover_url: entry.item.cover_url ?? null,
        })),
      },
    };
  });
}
