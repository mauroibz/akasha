import { apiFailure, jsonOrApiError, request } from "./request";
import type { components } from "./schema";

/** A library filter kept under a name (Sprint 100). `query` is the library's URL query. */
export type SavedView = components["schemas"]["SavedViewResponse"];

export function getViews(signal?: AbortSignal) {
  return request("/api/views", { signal }).then((r) =>
    jsonOrApiError<SavedView[]>(r, "Saved views could not be loaded"),
  );
}

export function saveView(name: string, query: string) {
  return request("/api/views", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ name, query }),
  }).then((r) => jsonOrApiError<SavedView>(r, "The view could not be saved"));
}

export function deleteView(id: number) {
  return request(`/api/views/${id}`, { method: "DELETE" }).then(async (r) => {
    if (!r.ok) throw await apiFailure(r, "The view could not be deleted");
  });
}
