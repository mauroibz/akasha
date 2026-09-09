import type { Shelf } from "./library";
import { request } from "./request";

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
}

async function jsonOrThrow<T>(
  response: Response,
  fallback: string,
): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(body?.error?.message ?? fallback);
  }
  return response.json() as Promise<T>;
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
  }).then((r) => {
    if (!r.ok) throw new Error("Shelf could not be deleted");
  });
}
