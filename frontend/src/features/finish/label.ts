import type { ItemType } from "@/api/library";
import { statusLabelFor } from "@/features/library/labels";
import { statusWith } from "@/features/rescore/rescore";

/**
 * The finish button's words (DEC-192): the action, in the domain's own word for its
 * finished status, so it is not read as the status itself. "Mark as read" on a book,
 * "Mark as watched" on a film.
 */
export function finishAction(
  itemType: string,
  types: ItemType[] | undefined,
): string {
  const finished = statusWith(itemType, types, "finished");
  if (!finished) return "Mark finished";
  return `Mark as ${statusLabelFor(itemType, types, finished).toLowerCase()}`;
}

/** The same action, naming what it acts on, for a screen reader. */
export function finishActionFor(
  title: string,
  itemType: string,
  types: ItemType[] | undefined,
): string {
  const action = finishAction(itemType, types);
  return action.startsWith("Mark as ")
    ? `Mark ${title} as ${action.slice("Mark as ".length)}`
    : `Mark ${title} finished`;
}
