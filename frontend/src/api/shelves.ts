import type { Shelf } from "./library";
import { apiFailure, jsonOrApiError, readApiError, request } from "./request";

export interface ShelfWithCount extends Shelf {
  entry_count: number;
  //: The shelf's own created/renamed time (Sprint 074) -- the nearest signal
  //: for "recently added to" without a new `entry_shelves` timestamp column.
  //: Optional for the same reason `covers` is: shelf-shaped values built
  //: elsewhere (`AddForm`, `ShelfPicker`) never carry it.
  updated_at?: string;
  //: Up to three cover URLs from the shelf's own members (Sprint 071).
  //: Optional: `AddForm` and `ShelfPicker` build shelf-shaped values of their
  //: own that never carry it, and `GET /api/shelves` always does.
  covers?: string[];
  //: Members grouped by item type (Sprint 074), keyed by domain id. Optional
  //: for the same reason `covers` is: `AddForm` and `ShelfPicker` build
  //: shelf-shaped values that never carry it.
  members_by_type?: Record<string, number>;
  //: Up to eight members as the shelf's ledge stands them up, and the shelf's
  //: two figures (Sprint 105). Optional for the same reason as `covers`.
  preview?: ShelfPreviewMember[];
  finished_count?: number;
  mean_score?: number | null;
}

export interface ShelfPreviewMember {
  entry_id: number;
  title: string;
  year: number | null;
  score: number | null;
  cover_url: string | null;
}

async function jsonOrThrow<T>(
  response: Response,
  fallback: string,
): Promise<T> {
  return jsonOrApiError<T>(response, fallback);
}

export function getShelves() {
  return request("/api/shelves").then((r) =>
    jsonOrThrow<ShelfWithCount[]>(r, "Shelves could not be loaded"),
  );
}

export function createShelf(name: string) {
  return request("/api/shelves", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then((r) => jsonOrThrow<ShelfWithCount>(r, "Shelf could not be created"));
}

export function renameShelf(id: number, name: string) {
  return request(`/api/shelves/${id}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then((r) => jsonOrThrow<ShelfWithCount>(r, "Shelf could not be renamed"));
}

export function deleteShelf(id: number) {
  return request(`/api/shelves/${id}`, {
    method: "DELETE",
  }).then(async (r) => {
    if (!r.ok) throw await apiFailure(r, "Shelf could not be deleted");
  });
}

/** A shelf the library already implies (Sprint 119, DEC-176). */
export interface ShelfSuggestion {
  key: string;
  kind: "creator" | "series" | "work";
  name: string;
  reason: string;
  members: ShelfPreviewMember[];
}

const json = { Accept: "application/json", "Content-Type": "application/json" };

export function getShelfSuggestions(signal?: AbortSignal) {
  return request("/api/shelves/suggestions", { signal }).then((r) =>
    jsonOrApiError<ShelfSuggestion[]>(r, "Suggestions could not be loaded"),
  );
}

export function acceptShelfSuggestion(key: string) {
  return request("/api/shelves/suggestions/accept", {
    method: "POST",
    headers: json,
    body: JSON.stringify({ key }),
  }).then((r) =>
    jsonOrApiError<ShelfWithCount>(r, "The shelf could not be made"),
  );
}

export async function dismissShelfSuggestion(key: string) {
  const response = await request("/api/shelves/suggestions/dismiss", {
    method: "POST",
    headers: json,
    body: JSON.stringify({ key }),
  });
  if (!response.ok)
    throw await readApiError(response, "Your answer could not be saved");
}
