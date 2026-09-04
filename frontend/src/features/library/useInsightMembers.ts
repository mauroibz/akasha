import { useQuery } from "@tanstack/react-query";

import { getLibraryPage } from "@/api/library";

/** How many of a row's entries a card shows before deferring to the library. */
export const memberPreview = 4;

/**
 * The entries behind one ranking row (Sprint 066).
 *
 * Exactly the request the row's library link already makes — the `key`/`value`
 * filter Sprint 065 built for it — asked for a handful and rendered in place. The
 * shipped screen's only interaction navigated away, so reading a ranking was
 * back-button ping-pong.
 *
 * Highest scored first, because a row's question is usually "which of these did I
 * like", and only when a row is actually opened: a page of six cards must not
 * fetch a page of entries per row on arrival.
 */
export function useInsightMembers(params: {
  type: string;
  insightKey: string;
  value: string;
  enabled: boolean;
}) {
  return useQuery({
    queryKey: ["insight-members", params.type, params.insightKey, params.value],
    enabled: params.enabled,
    queryFn: ({ signal }) =>
      getLibraryPage(
        {
          statuses: [],
          shelves: [],
          formats: [],
          types: [params.type],
          query: "",
          sort: "score",
          order: "desc",
          key: params.insightKey,
          value: params.value,
        },
        undefined,
        signal,
        memberPreview,
      ),
  });
}
