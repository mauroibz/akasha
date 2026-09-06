import { useQuery } from "@tanstack/react-query";

import {
  getScoreDistribution,
  type EntryFormat,
  type EntryStatus,
  type ScoreDistribution,
} from "@/api/library";

/**
 * The score distribution band (Sprint 073 deliverable 4) — the one new number in
 * the proposal, and the sprint's only backend addition. One request, honouring
 * the same filters a ranking does (Sprint 067 deliverable 5's "within my current
 * filters", off by default).
 */
export function useScoreDistribution(params: {
  type: string;
  statuses?: EntryStatus[];
  shelves?: string[];
  formats?: EntryFormat[];
  q?: string;
}) {
  return useQuery<ScoreDistribution>({
    queryKey: [
      "insights-scores",
      params.type,
      params.statuses,
      params.shelves,
      params.formats,
      params.q,
    ],
    queryFn: () =>
      getScoreDistribution({
        type: params.type,
        statuses: params.statuses,
        shelves: params.shelves,
        formats: params.formats,
        q: params.q,
      }),
    enabled: Boolean(params.type),
  });
}
