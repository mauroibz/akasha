import type { OutlinePart, ProgressMarks } from "@/api/library";

/**
 * Episode and chapter marks, as the detail page draws and changes them (DEC-171).
 *
 * Marks are keyed by part ("1" is season one, or the only part of a book) and hold
 * the numbers done. Every function here returns a new object with each part's
 * numbers sorted and unique and no empty parts, which is the shape the server
 * stores, so a write sends exactly what is drawn.
 */

function normalized(marks: ProgressMarks): ProgressMarks {
  const result: ProgressMarks = {};
  for (const key of Object.keys(marks).sort((a, b) => Number(a) - Number(b))) {
    const numbers = [...new Set(marks[key])].sort((a, b) => a - b);
    if (numbers.length) result[key] = numbers;
  }
  return result;
}

const range = (size: number) => Array.from({ length: size }, (_, i) => i + 1);

/**
 * The marks to draw: the stored ones, or else an imported count as the first N in
 * outline order. An imported count says how many, not which; reading it as "from the
 * start" is the honest guess, and it is stored as marks only when the owner touches
 * a light.
 */
export function drawnMarks(
  stored: ProgressMarks | null | undefined,
  progress: number | null | undefined,
  outline: OutlinePart[],
): ProgressMarks {
  if (stored && Object.keys(stored).length) return normalized(stored);
  let left = progress ?? 0;
  const result: ProgressMarks = {};
  for (const part of outline) {
    if (left <= 0) break;
    const take = Math.min(left, part.size);
    result[String(part.part)] = range(take);
    left -= take;
  }
  return result;
}

export function countMarks(marks: ProgressMarks): number {
  return Object.values(marks).reduce((sum, numbers) => sum + numbers.length, 0);
}

export function isMarked(
  marks: ProgressMarks,
  part: number,
  number: number,
): boolean {
  return marks[String(part)]?.includes(number) ?? false;
}

export function toggleMark(
  marks: ProgressMarks,
  part: number,
  number: number,
): ProgressMarks {
  const key = String(part);
  const current = marks[key] ?? [];
  const next = current.includes(number)
    ? current.filter((value) => value !== number)
    : [...current, number];
  return normalized({ ...marks, [key]: next });
}

/** Whether a part is fully marked, partly, or not at all. */
export function partState(
  marks: ProgressMarks,
  part: OutlinePart,
): "all" | "some" | "none" {
  const done = range(part.size).filter((n) => isMarked(marks, part.part, n));
  if (done.length === part.size) return "all";
  return done.length ? "some" : "none";
}

/**
 * A whole season at once: fill it, or clear it when it is all marked already. Marks
 * past the part's size (a refresh shrank it) are left as they are.
 */
export function togglePart(
  marks: ProgressMarks,
  part: OutlinePart,
): ProgressMarks {
  const key = String(part.part);
  const current = marks[key] ?? [];
  const beyond = current.filter((n) => n > part.size);
  const next =
    partState(marks, part) === "all"
      ? beyond
      : [...current, ...range(part.size)];
  return normalized({ ...marks, [key]: next });
}

/**
 * "I stopped here": everything up to and including this one, in outline order. What
 * the question asked on dropping an entry writes (DEC-172).
 */
export function fillThrough(
  outline: OutlinePart[],
  part: number,
  number: number,
): ProgressMarks {
  const result: ProgressMarks = {};
  for (const row of outline) {
    if (row.part === part) {
      result[String(row.part)] = range(Math.min(number, row.size));
      break;
    }
    result[String(row.part)] = range(row.size);
  }
  return normalized(result);
}

export const capital = (text: string) =>
  text.charAt(0).toUpperCase() + text.slice(1);
