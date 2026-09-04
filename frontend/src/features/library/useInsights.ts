import { useQueries } from "@tanstack/react-query";

import { getInsights, type Insight } from "@/api/library";

/**
 * How deep a ranking is fetched.
 *
 * The server's maximum, and deliberately the whole distribution rather than a page
 * of it: the screen sorts by both count and score from one response (`orderRows`)
 * and decides which keys are worth a card from the shape of the whole ranking
 * (`keyLead`), and neither is answerable from the top 50. A row is six small
 * fields, so 200 of them is a few kilobytes; `rank()` computes every group
 * server-side either way and only the page size changes.
 *
 * A domain with more than 200 distinct values for one key is ranked over its 200
 * most-held, and `next_cursor` is how a card knows to say so.
 */
export const insightDepth = 200;

/**
 * Every one of a domain's rankings, one request each, in parallel (Sprint 066).
 *
 * Sprint 065 asked one question per visit: a key picker, a refetch, and no way to
 * see two answers beside each other. The screen answers on arrival instead, which
 * means every key at once. `useQueries` rather than a batched endpoint because
 * a personal library's rankings are cheap and the batch parameter is deliberately
 * only added if the request count is measured to cost something (sprint
 * deliverable 9) — an endpoint change made on a guess is the change hardest to
 * take back.
 *
 * `metric` is not a parameter. `count` is asked for because it is the metric that
 * returns *every* group, including the ones too thinly rated for a score order to
 * place; the ordering itself is the client's, over data it already holds.
 */
export function useInsights(params: {
  type: string;
  keys: string[];
  includeSuppressed: boolean;
}) {
  return useQueries({
    queries: params.keys.map((key) => ({
      queryKey: ["insights", params.type, key, params.includeSuppressed],
      queryFn: (): Promise<Insight> =>
        getInsights({
          type: params.type,
          key,
          metric: "count" as const,
          includeSuppressed: params.includeSuppressed,
          limit: insightDepth,
        }),
      enabled: Boolean(params.type && key),
    })),
  });
}
