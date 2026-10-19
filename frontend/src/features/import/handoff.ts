/**
 * Files dropped on the Add screen, on their way to the import screen (Sprint 086).
 *
 * In memory and taken exactly once: a `File` is a handle to something on the
 * reader's disk, so it travels as a reference rather than through router state or
 * storage, and a reload or a later visit starts empty instead of resurrecting a
 * drop the reader already moved past.
 */
let handed: { importerId: string; files: File[] } | null = null;

export function handFiles(importerId: string, files: File[]): void {
  handed = { importerId, files };
}

/** The files handed to this connector, once; `null` when there are none. */
export function takeHandedFiles(importerId: string): File[] | null {
  if (!handed || handed.importerId !== importerId) return null;
  const { files } = handed;
  handed = null;
  return files;
}
