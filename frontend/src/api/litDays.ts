import type { LibraryEntry } from "./library";
import { apiFailure, jsonOrApiError, request } from "./request";

/** A lit day and what it was for (Sprint 147, DEC-193). */
export interface LitDay {
  /** `YYYY-MM-DD`. */
  day: string;
  entries: LibraryEntry[];
}

function zone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return "";
  }
}

export function getLitDays(from: string, to: string, signal?: AbortSignal) {
  return request(`/api/lit-days?from=${from}&to=${to}`, { signal }).then((r) =>
    jsonOrApiError<{ days: LitDay[] }>(r, "The calendar could not be loaded"),
  );
}

/** Light a day by hand: for these entries, or for nothing in particular. */
export function lightDay(day: string, entryIds: number[]) {
  const tz = zone();
  return request(
    `/api/lit-days/${day}${tz ? `?tz=${encodeURIComponent(tz)}` : ""}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entry_ids: entryIds }),
    },
  ).then((r) => jsonOrApiError<LitDay>(r, "The day could not be lit"));
}

export function unlightDay(day: string) {
  return request(`/api/lit-days/${day}`, { method: "DELETE" }).then(
    async (r) => {
      if (!r.ok) throw await apiFailure(r, "The day could not be unlit");
    },
  );
}
