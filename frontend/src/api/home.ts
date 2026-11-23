import type { LibraryEntry } from "./library";
import type { Suggestion } from "./suggestions";
import { jsonOrApiError, request } from "./request";
import type { components } from "./schema";

type Schemas = components["schemas"];

export type HomeCover = Schemas["HomeCover"];
export type HomeYearGoal = Schemas["HomeYearGoal"];
export type HomeLibraryYear = Schemas["HomeLibraryYear"];
export type HomeShelfModule = Schemas["HomeShelfModule"];

/** The schema's entries, read as the library's own entry shape. */
export type PileReason = Schemas["PileReason"];
/** A pick from the ranked pile (Sprint 132): Up next, a goal's picks, `/api/pile`. */
export type HomeNext = Omit<Schemas["PilePick"], "entry"> & {
  entry: LibraryEntry;
};
export type HomeGreeting = Omit<Schemas["HomeGreeting"], "active"> & {
  active: { entry: LibraryEntry; day: number | null } | null;
};

export type HomeLatelyRow = Omit<Schemas["HomeLatelyRow"], "entry"> & {
  entry: LibraryEntry;
};
export type HomeQuestion = Omit<Schemas["HomeQuestion"], "entry"> & {
  entry: LibraryEntry;
};
/**
 * The Library's front in one read (Sprints 130-131, DEC-183; the Library's since
 * Sprint 141, DEC-193): the greeting, what is under way, what happened lately, and
 * every showcase's payload, stored data only. A showcase the person hid comes back
 * empty or `null`, unread.
 */
export interface Home {
  greeting: HomeGreeting;
  now: LibraryEntry[];
  lately: HomeLatelyRow[];
  next: HomeNext[];
  question: HomeQuestion | null;
  /** *More like this* (Sprint 134): found, unanswered suggestions, newest first. */
  suggested?: Suggestion[] | null;
  /** The libraries' years the person shows (Sprint 138). */
  library_years?: HomeLibraryYear[];
  /** The shelves the person placed (Sprint 138). */
  shelf_modules?: HomeShelfModule[];
}

/** The person's own zone, so Home's today and Lately's days are theirs (Sprint 132). */
function zone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return "";
  }
}

export function getHome(signal?: AbortSignal) {
  const tz = zone();
  const url = tz ? `/api/home?tz=${encodeURIComponent(tz)}` : "/api/home";
  return request(url, { signal }).then((r) =>
    jsonOrApiError<Home>(r, "Home could not be loaded"),
  );
}

export type ModuleLayout = Schemas["HomeModuleLayout"];
export type ModuleSize = ModuleLayout["size"];
export type HomeLayout = Schemas["HomeLayoutResponse"];

/** This person's Home layout (Sprint 131): order, size, hidden. */
export function getHomeLayout(signal?: AbortSignal) {
  return request("/api/home/layout", { signal }).then((r) =>
    jsonOrApiError<HomeLayout>(r, "Your Home layout could not be loaded"),
  );
}

export function putHomeLayout(modules: ModuleLayout[]) {
  return request("/api/home/layout", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modules }),
  }).then((r) =>
    jsonOrApiError<HomeLayout>(r, "Your Home layout could not be saved"),
  );
}

/**
 * The whole pile, ranked (DEC-192): every library's waiting entries in the order *Up
 * next* would offer them, for the pile's own page.
 */
export function getPile(limit: number, signal?: AbortSignal) {
  return request(`/api/pile?limit=${limit}`, { signal }).then((r) =>
    jsonOrApiError<HomeNext[]>(r, "The pile could not be loaded"),
  );
}
