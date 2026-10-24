import type { ItemType, LibraryEntry } from "@/api/library";
import { hasEntryField } from "@/features/library/labels";
import { statusWith } from "@/features/rescore/rescore";

/** A gap in the reading data that can be asked about (Sprint 124, DEC-179). */
export type Question =
  "date_finished" | "formats" | "location" | "date_started";

/**
 * The gaps worth asking about, most useful first: when something was finished (the
 * Diary and the year in review read it), how it is held, where it is, when it began.
 * Nothing known is asked, nothing the owner said they do not remember, nothing the
 * domain does not have, and no date before there is a pass to date.
 */
export function questionsFor(
  entry: Pick<
    LibraryEntry,
    | "status"
    | "date_started"
    | "date_finished"
    | "formats"
    | "location"
    | "unknown_fields"
    | "item"
  >,
  types: ItemType[] | undefined,
): Question[] {
  const type = entry.item.type;
  const forgotten = new Set(entry.unknown_fields ?? []);
  const finished = statusWith(type, types, "finished") === entry.status;
  const underWay = statusWith(type, types, "in_progress") === entry.status;
  const planned = statusWith(type, types, "planned") === entry.status;
  const formats =
    (Array.isArray(types) ? types : []).find((row) => row.id === type)
      ?.formats ?? [];
  const asked: Question[] = [];
  const ask = (question: Question, when: boolean) => {
    if (when && !forgotten.has(question)) asked.push(question);
  };
  ask(
    "date_finished",
    finished &&
      !entry.date_finished &&
      hasEntryField(type, types, "date_finished"),
  );
  ask("formats", formats.length > 0 && (entry.formats ?? []).length === 0);
  ask("location", !entry.location && !planned && entry.status !== "unsorted");
  ask(
    "date_started",
    (finished || underWay) &&
      !entry.date_started &&
      hasEntryField(type, types, "date_started"),
  );
  return asked;
}
