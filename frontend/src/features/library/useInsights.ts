import { useQuery } from "@tanstack/react-query";

import { getInsights } from "@/api/library";

/**
 * One domain's ranking by one key and metric — refetched whenever any of those
 * change, since each is a different question to the server rather than a page of
 * the same one (Sprint 065).
 */
export function useInsights(params: {
  type: string;
  key: string;
  metric: "count" | "score";
  minRated: number;
  includeSuppressed: boolean;
}) {
  return useQuery({
    queryKey: [
      "insights",
      params.type,
      params.key,
      params.metric,
      params.minRated,
      params.includeSuppressed,
    ],
    queryFn: () =>
      getInsights({
        type: params.type,
        key: params.key,
        metric: params.metric,
        minRated: params.minRated,
        includeSuppressed: params.includeSuppressed,
      }),
    enabled: Boolean(params.type && params.key),
  });
}
