import { jsonOrApiError, request } from "./request";
import type { components } from "./schema";

type Schemas = components["schemas"];

/** One thing a source suggested (Sprint 133-134), as stored. */
export type Suggestion = Schemas["SuggestionResponse"];
/** One person's request to one source, with what it stored. */
export type SuggestionRound = Schemas["RoundResponse"];
export type SuggestionAnswer = NonNullable<Suggestion["answer"]>;

/** A round in one of these states is over; the others are on their way. */
export const FINISHED_ROUNDS: ReadonlySet<SuggestionRound["status"]> = new Set([
  "done",
  "failed",
  "over_budget",
  "not_configured",
]);

const JSON_HEADERS = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

/**
 * *More like this* on one entry: a round under a day old again, or a new one
 * queued (202). `refresh` always asks again.
 */
export function moreLikeThis(
  entryId: number,
  options: { refresh?: boolean; source?: string } = {},
): Promise<SuggestionRound> {
  const query = new URLSearchParams();
  if (options.refresh) query.set("refresh", "true");
  if (options.source) query.set("source", options.source);
  const suffix = query.size ? `?${query.toString()}` : "";
  return request(`/api/entries/${entryId}/more-like-this${suffix}`, {
    method: "POST",
    headers: { Accept: "application/json" },
  }).then((r) =>
    jsonOrApiError<SuggestionRound>(r, "Suggestions could not be asked for"),
  );
}

export function getSuggestionRound(
  roundId: number,
  signal?: AbortSignal,
): Promise<SuggestionRound> {
  return request(`/api/suggestion-rounds/${roundId}`, {
    signal,
    headers: { Accept: "application/json" },
  }).then((r) =>
    jsonOrApiError<SuggestionRound>(r, "Suggestions could not be loaded"),
  );
}

/** Record an answer; `want` adds it to the list first. `null` takes it back. */
export function answerSuggestion(
  suggestionId: number,
  answer: SuggestionAnswer | null,
): Promise<Suggestion> {
  return request(`/api/suggestions/${suggestionId}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify({ answer }),
  }).then((r) => jsonOrApiError<Suggestion>(r, "Your answer was not saved"));
}

/** Find a pending suggestion in its providers now (a background job). */
export function enrichSuggestion(
  suggestionId: number,
): Promise<{ suggestion: Suggestion; job_id: string | null }> {
  return request(`/api/suggestions/${suggestionId}/enrich`, {
    method: "POST",
    headers: { Accept: "application/json" },
  }).then((r) =>
    jsonOrApiError<{ suggestion: Suggestion; job_id: string | null }>(
      r,
      "It could not be looked up",
    ),
  );
}
