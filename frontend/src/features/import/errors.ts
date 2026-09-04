import type { ItemType } from "@/api/library";
import {
  entryFieldLabel,
  type EntryFieldName,
} from "@/features/library/labels";

/**
 * What a preview row's failed field actually is, in the domain's own words
 * (proposal §3.6, finding 3).
 *
 * A reader's own connector — `imdb.py`, `letterboxd.py`, `trakt.py` — already
 * passes a human sentence fragment for the column it read (`"Your Rating"`,
 * `"Watched Date"`); an older one — `goodreads.py`, `calibre.py`,
 * `myanimelist.py` — passes its own internal field name (`isbn`, `my_rating`,
 * `series_animedb_id`). Both are handled the same way here: a field already
 * declared by the target domain (an entry field or a metadata `FieldSpec`)
 * renders under its declared label; anything else — including a name that
 * already reads as a sentence fragment — is humanized rather than shown raw.
 * No backend change accompanies this (the sprint's own verification section:
 * no Python file changes), so this is the honest ceiling of what a purely
 * presentational fix can know without a connector declaring its own field
 * vocabulary.
 */
const KNOWN_FIELD_LABELS: Record<string, string> = {
  title: "Title",
  isbn: "ISBN",
  rating: "Rating",
  my_rating: "Rating",
  date_read: "Date read",
  series_animedb_id: "MyAnimeList id",
  series_title: "Title",
};

const ENTRY_FIELDS = new Set<EntryFieldName>([
  "date_started",
  "date_finished",
  "reread_count",
]);

function isEntryField(field: string): field is EntryFieldName {
  return ENTRY_FIELDS.has(field as EntryFieldName);
}

/** `date_read` -> `Date read`; `Your Rating` -> `Your Rating` (unchanged). */
function humanize(raw: string): string {
  const spaced = raw.replace(/[_-]+/g, " ").trim();
  return spaced.length ? spaced[0].toUpperCase() + spaced.slice(1) : spaced;
}

/** The domain's declared label for one failed field, or the best honest guess. */
export function fieldLabel(field: string, type: ItemType | undefined): string {
  if (isEntryField(field)) {
    return entryFieldLabel(type?.id ?? "", type ? [type] : undefined, field);
  }
  const declared = type?.fields.find((candidate) => candidate.name === field);
  if (declared) return declared.label;
  return KNOWN_FIELD_LABELS[field] ?? humanize(field);
}

/**
 * The connector's declared wording for the error, one sentence fragment per
 * code across every reader that raises row-level field errors today
 * (`goodreads.py`, `calibre.py`, `myanimelist.py`, `letterboxd.py`,
 * `imdb.py`, `trakt.py`).
 */
const ERROR_WORDING: Record<string, string> = {
  required: "is required",
  invalid_date: "isn't a date we can read",
  invalid_year: "isn't a valid year",
  invalid_isbn: "isn't a valid ISBN",
  invalid_rating: "isn't a valid rating",
  invalid_integer: "isn't a whole number",
  invalid_id: "isn't a recognized id",
  invalid_identifier: "isn't a recognized id",
  out_of_range: "is outside the range this accepts",
  too_long: "is too long",
  malformed_row: "could not be read",
  duplicate_series_id: "is used by another row in this import",
  duplicate_identifier: "is used by another row in this import",
  conflicting_title: "does not match this import's own title for it",
  conflicting_year: "does not match this import's own year for it",
  unusable_uri: "is not a usable link",
  rating_not_a_number: "isn't a number",
  rating_out_of_range: "is outside the range this accepts",
};

function errorWording(code: string): string {
  return ERROR_WORDING[code] ?? `isn't valid (${humanize(code).toLowerCase()})`;
}

/**
 * One legible sentence for a failed preview row, naming the domain's declared
 * label for the field and the connector's declared wording for the error —
 * never the raw `field: code` a reader used to see (finding 3, AC3).
 */
export function describeRowError(
  row: { field: string; code: string },
  type: ItemType | undefined,
): string {
  return `${fieldLabel(row.field, type)} ${errorWording(row.code)}.`;
}
