import { useQuery } from "@tanstack/react-query";

import { getInsights } from "@/api/library";

/**
 * How deep a ranking is fetched.
 *
 * The server's maximum, and deliberately the whole distribution rather than a
 * page of it: the screen sorts by both count and score from one response
 * (`orderRows`) and decides which keys are worth a card from the shape of the
 * whole ranking, and neither is answerable from the top 50. A row is six small
 * fields, so 200 of them is a few kilobytes; `rank()` computes every group
 * server-side either way and only the page size changes.
 *
 * A domain with more than 200 distinct values for one key is ranked over its 200
 * most-held, and `next_cursor` is how the screen knows to say so.
 */
export const insightDepth = 200;

/**
 * One domain's ranking by one key — fetched once, read in either order.
 *
 * `metric` is deliberately not a parameter (Sprint 066). Sprint 065 made it one,
 * which meant the count and score orders were two different requests returning
 * two different subsets, and choosing either threw the other's numbers away.
 * `count` is asked for because it is the metric that returns *every* group,
 * including the ones too thinly rated for a score order to place; the ordering
 * itself is the client's, over data it already holds.
 */
export function useInsights(params: {
  type: string;
  key: string;
  includeSuppressed: boolean;
}) {
  return useQuery({
    queryKey: ["insights", params.type, params.key, params.includeSuppressed],
    queryFn: () =>
      getInsights({
        type: params.type,
        key: params.key,
        metric: "count",
        includeSuppressed: params.includeSuppressed,
        limit: insightDepth,
      }),
    enabled: Boolean(params.type && params.key),
  });
}
