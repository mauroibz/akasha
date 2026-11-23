import type { LibraryEntry } from "./library";
import { jsonOrApiError, request } from "./request";
import type { components } from "./schema";

type Schemas = components["schemas"];

export type HomeCover = Schemas["HomeCover"];
export type HomeMonth = Schemas["HomeMonth"];
export type HomeYear = Schemas["HomeYear"];
export type HomeYearGoal = Schemas["HomeYearGoal"];
export type HomeDomainTile = Schemas["HomeDomainTile"];
export type HomeTidy = Schemas["HomeTidy"];
export type HomeShelf = Schemas["HomeShelf"];

/** The schema's entries, read as the library's own entry shape. */
export type HomeNext = Omit<Schemas["HomeNext"], "entry"> & {
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
export type HomeLoan = Omit<Schemas["HomeLoan"], "entry"> & {
  entry: LibraryEntry;
};
export interface HomeLent {
  total: number;
  loans: HomeLoan[];
}

/**
 * Home's one read (Sprints 130-131, DEC-183): every module's payload, stored data
 * only. A module the person hid comes back empty or `null`, unread.
 */
export interface Home {
  greeting: HomeGreeting;
  now: LibraryEntry[];
  next: HomeNext[];
  year: HomeYear | null;
  domains: HomeDomainTile[];
  lately: HomeLatelyRow[] | null;
  tidy: HomeTidy | null;
  question: HomeQuestion | null;
  shelves: HomeShelf[] | null;
  lent: HomeLent | null;
}

export function getHome(signal?: AbortSignal) {
  return request("/api/home", { signal }).then((r) =>
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
