import { apiFailure, jsonOrApiError, request } from "./request";
import type { components } from "./schema";

/** A gentle goal for one domain (Sprint 103, DEC-169). */
export type Goal = components["schemas"]["GoalResponse"];
export type GoalProgress = components["schemas"]["GoalProgressResponse"];
export type GoalPick = components["schemas"]["GoalPickResponse"];
export type GoalPeriod = Goal["period"];

export function getGoals(signal?: AbortSignal) {
  return request("/api/goals", { signal }).then((r) =>
    jsonOrApiError<Goal[]>(r, "Goals could not be loaded"),
  );
}

export function setGoal(
  itemType: string,
  body: { count: number; period: GoalPeriod; suggest: boolean },
) {
  return request(`/api/goals/${encodeURIComponent(itemType)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => jsonOrApiError<Goal>(r, "The goal could not be saved"));
}

export async function deleteGoal(itemType: string): Promise<void> {
  const response = await request(`/api/goals/${encodeURIComponent(itemType)}`, {
    method: "DELETE",
  });
  if (!response.ok)
    throw await apiFailure(response, "The goal could not be removed");
}

export function getGoalProgress(
  itemType: string,
  year: number,
  signal?: AbortSignal,
) {
  return request(
    `/api/goals/${encodeURIComponent(itemType)}/progress?year=${year}`,
    { signal },
  ).then((r) =>
    jsonOrApiError<GoalProgress>(r, "Progress could not be loaded"),
  );
}

export function getGoalPicks(itemType: string, signal?: AbortSignal) {
  return request(`/api/goals/${encodeURIComponent(itemType)}/picks?limit=8`, {
    signal,
  }).then((r) => jsonOrApiError<GoalPick[]>(r, "Picks could not be loaded"));
}
