import type { LibraryEntry } from "./library";
import { jsonOrApiError, request } from "./request";
import type { components } from "./schema";

type Schemas = components["schemas"];

export type HomeCover = Schemas["HomeCover"];
export type HomeMonth = Schemas["HomeMonth"];
export type HomeYear = Schemas["HomeYear"];
export type HomeYearGoal = Schemas["HomeYearGoal"];
export type HomeDomainTile = Schemas["HomeDomainTile"];

/** The schema's entries, read as the library's own entry shape. */
export type HomeNext = Omit<Schemas["HomeNext"], "entry"> & {
  entry: LibraryEntry;
};
export type HomeGreeting = Omit<Schemas["HomeGreeting"], "active"> & {
  active: { entry: LibraryEntry; day: number | null } | null;
};

/** Home's one read (Sprint 130, DEC-183): every module's payload, stored data only. */
export interface Home {
  greeting: HomeGreeting;
  now: LibraryEntry[];
  next: HomeNext[];
  year: HomeYear;
  domains: HomeDomainTile[];
}

export function getHome(signal?: AbortSignal) {
  return request("/api/home", { signal }).then((r) =>
    jsonOrApiError<Home>(r, "Home could not be loaded"),
  );
}
