/**
 * Turning a chosen Calibre folder into the few files worth uploading.
 *
 * A browser hands over the whole tree — ebooks, `metadata.opf`, and Calibre's own
 * hidden directories. Measured on a real library, that is 32 MB of which 2.4 MB
 * matters. The filter is what makes this flow viable at all (DEC-081).
 */

/** One file selected for upload, under the relative path the server will see. */
export interface BundleMember {
  readonly path: string;
  readonly file: File;
}

export interface CalibreBundle {
  readonly members: BundleMember[];
  readonly database: BundleMember | null;
  readonly covers: number;
  readonly bytes: number;
  /** Everything the filter left behind, for the "and nothing else" line. */
  readonly skipped: number;
}

/**
 * `webkitRelativePath` is prefixed with the name of the folder the reader picked,
 * which is theirs and not part of the library's shape. Strip it so `metadata.db`
 * is at the root whatever the folder happens to be called.
 */
function relativePath(file: File): string {
  const full = file.webkitRelativePath || file.name;
  const cut = full.indexOf("/");
  return cut === -1 ? full : full.slice(cut + 1);
}

/**
 * Exactly `metadata.db` at the root, and any `cover.jpg` below it.
 *
 * Hidden segments are dropped rather than uploaded: `.caltrash/b/1/cover.jpg` is a
 * deleted book's cover and importing it would resurrect something the reader threw
 * away. The server refuses the same set again — this filter is for the reader's
 * bandwidth, not for their safety.
 */
export function calibreBundle(files: readonly File[]): CalibreBundle {
  const members: BundleMember[] = [];
  let skipped = 0;
  for (const file of files) {
    const path = relativePath(file);
    const segments = path.split("/");
    const hidden = segments.some((segment) => segment.startsWith("."));
    const wanted =
      !hidden &&
      (path === "metadata.db" ||
        (segments.length >= 2 &&
          segments[segments.length - 1] === "cover.jpg"));
    if (wanted) members.push({ path, file });
    else skipped += 1;
  }
  const database =
    members.find((member) => member.path === "metadata.db") ?? null;
  return {
    members,
    database,
    covers: members.filter((member) => member.path !== "metadata.db").length,
    bytes: members.reduce((total, member) => total + member.file.size, 0),
    skipped,
  };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const megabytes = bytes / (1024 * 1024);
  return megabytes >= 1
    ? `${megabytes.toFixed(1)} MB`
    : `${Math.round(bytes / 1024)} KB`;
}
