import type {
  EntryStatus,
  ItemType,
  LibraryEntry,
  LibraryFilters,
  SortKey,
} from "@/api/library";
import { statusesFor } from "@/features/library/labels";

/**
 * What the inbox and its deck both read from the address: the same filter, so
 * *One at a time* goes through exactly the rows the list was showing (DEC-170).
 */
export function triageFiltersFromParams(
  params: URLSearchParams,
): LibraryFilters {
  const statuses = params.getAll("status") as EntryStatus[];
  return {
    statuses: statuses.length ? statuses : ["unsorted"],
    shelves: params.getAll("shelf"),
    formats: [],
    // Triage has no domain tab: the inbox is one queue whatever landed in it.
    types: [],
    query: params.get("q") ?? "",
    sort: (params.get("sort") as SortKey) ?? "date_added",
    order: (params.get("order") as "asc" | "desc") ?? "desc",
    key: "",
    value: "",
    valueLabel: "",
  };
}

export const STATUS_DRAFTS_STORAGE_KEY = "akasha.triage.status-drafts.v1";

/** The list's unsaved row targets, kept per browser tab. */
export function loadStatusDrafts(): Map<number, EntryStatus> {
  try {
    const stored = window.sessionStorage.getItem(STATUS_DRAFTS_STORAGE_KEY);
    if (!stored) return new Map();
    const parsed: unknown = JSON.parse(stored);
    if (!Array.isArray(parsed)) return new Map();
    return new Map(
      parsed.filter(
        (draft): draft is [number, EntryStatus] =>
          Array.isArray(draft) &&
          Number.isInteger(draft[0]) &&
          typeof draft[1] === "string",
      ),
    );
  } catch {
    return new Map();
  }
}

export function saveStatusDrafts(drafts: Map<number, EntryStatus>) {
  try {
    if (drafts.size === 0) {
      window.sessionStorage.removeItem(STATUS_DRAFTS_STORAGE_KEY);
    } else {
      window.sessionStorage.setItem(
        STATUS_DRAFTS_STORAGE_KEY,
        JSON.stringify(Array.from(drafts)),
      );
    }
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts. The
    // row still works for the current visit; only cross-navigation recovery is lost.
  }
}

/**
 * Where a row goes if it is applied untouched: the importer's suggestion, else
 * the domain's declared default (product spec, *Triage*). Inbox is never it.
 */
export function originalTargetFor(
  entry: LibraryEntry,
  types: ItemType[] | undefined,
): EntryStatus {
  const domainDefault =
    (Array.isArray(types)
      ? types.find((type) => type.id === entry.item.type)?.default_status
      : undefined) ??
    statusesFor(entry.item.type, types).find((status) => status.choosable)
      ?.value ??
    entry.status;
  return entry.suggested_status ?? domainDefault;
}

export const PASSED_STORAGE_KEY = "akasha.triage.passed.v1";

/** The entries passed in this tab, oldest pass first. */
export function loadPassed(): number[] {
  try {
    const parsed: unknown = JSON.parse(
      window.sessionStorage.getItem(PASSED_STORAGE_KEY) ?? "[]",
    );
    return Array.isArray(parsed)
      ? parsed.filter((id): id is number => Number.isInteger(id))
      : [];
  } catch {
    return [];
  }
}

export function savePassed(passed: number[]) {
  try {
    if (passed.length === 0)
      window.sessionStorage.removeItem(PASSED_STORAGE_KEY);
    else
      window.sessionStorage.setItem(PASSED_STORAGE_KEY, JSON.stringify(passed));
  } catch {
    // As above: a deck without storage forgets its passes on reload, nothing more.
  }
}

/**
 * The cards still to come in this round, in the inbox's own order.
 *
 * A filed entry has left; a passed one waits for the next round. Both are kept
 * out by id rather than by status, because the list behind the deck is not
 * refetched card by card and still holds them as `unsorted`.
 */
export function deckQueue(
  entries: readonly LibraryEntry[],
  filed: ReadonlySet<number>,
  passed: ReadonlySet<number>,
): LibraryEntry[] {
  return entries.filter(
    (entry) => !filed.has(entry.id) && !passed.has(entry.id),
  );
}

/** One card's decision as the owner has left it on screen. */
export interface CardDraft {
  status: EntryStatus;
  score: number | null;
  /** A score is written only when touched, so a provisional one stays provisional. */
  scoreTouched: boolean;
  shelfIds: number[];
}

export function draftFor(
  entry: LibraryEntry,
  types: ItemType[] | undefined,
  drafts: Map<number, EntryStatus>,
): CardDraft {
  return {
    status: drafts.get(entry.id) ?? originalTargetFor(entry, types),
    score: entry.score,
    scoreTouched: false,
    shelfIds: entry.shelves.map((shelf) => shelf.id),
  };
}

function sameSet(a: readonly number[], b: readonly number[]) {
  return a.length === b.length && a.every((id) => b.includes(id));
}

/** The one PATCH that files a card: status always, the rest only if changed. */
export function filingChanges(entry: LibraryEntry, draft: CardDraft) {
  const changes: {
    status: EntryStatus;
    score?: number | null;
    shelf_ids?: number[];
  } = { status: draft.status };
  if (draft.scoreTouched) changes.score = draft.score;
  const before = entry.shelves.map((shelf) => shelf.id);
  if (!sameSet(before, draft.shelfIds)) changes.shelf_ids = draft.shelfIds;
  return changes;
}

/** The PATCH that puts a filed card back as it was. */
export function undoChanges(
  entry: LibraryEntry,
  filed: ReturnType<typeof filingChanges>,
) {
  const changes: {
    status: EntryStatus;
    score?: number | null;
    score_provisional?: boolean;
    shelf_ids?: number[];
  } = { status: entry.status };
  if ("score" in filed) {
    changes.score = entry.score;
    // A filed score confirms the import's guess; the undo makes it a guess again.
    if (entry.score !== null && entry.score_provisional)
      changes.score_provisional = true;
  }
  if ("shelf_ids" in filed)
    changes.shelf_ids = entry.shelves.map((shelf) => shelf.id);
  return changes;
}
