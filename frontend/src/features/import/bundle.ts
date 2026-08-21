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
  /** Preferred, under-cap ebooks that will be attached after commit. */
  readonly ebooks: BundleMember[];
  readonly ebookBytes: number;
  /** Preferred ebooks that were deliberately left behind because of the cap. */
  readonly overCap: BundleMember[];
  readonly bytes: number;
  /** Everything the filter left behind, for the "and nothing else" line. */
  readonly skipped: number;
}

export interface CalibreBundleOptions {
  readonly attachEbooks?: boolean;
  readonly attachmentMaxBytes?: number;
}

const EBOOK_FORMATS = [
  "epub",
  "azw3",
  "mobi",
  "pdf",
  "cbz",
  "cbr",
  "txt",
] as const;

function ebookRank(path: string): number | null {
  const filename = path.split("/").at(-1) ?? "";
  const extension = filename.includes(".")
    ? filename.split(".").at(-1)?.toLowerCase()
    : undefined;
  const rank = EBOOK_FORMATS.indexOf(
    extension as (typeof EBOOK_FORMATS)[number],
  );
  return rank === -1 ? null : rank;
}

/** Whether this member belongs to the post-commit attachment phase. */
export function isEbookMember(member: BundleMember): boolean {
  return ebookRank(member.path) !== null;
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
export function calibreBundle(
  files: readonly File[],
  options: CalibreBundleOptions = {},
): CalibreBundle {
  const sourceMembers: BundleMember[] = [];
  const preferredByDirectory = new Map<
    string,
    { member: BundleMember; rank: number }
  >();
  for (const file of files) {
    const path = relativePath(file);
    const segments = path.split("/");
    const hidden = segments.some((segment) => segment.startsWith("."));
    if (hidden) continue;
    const member = { path, file };
    if (
      path === "metadata.db" ||
      (segments.length >= 2 && segments[segments.length - 1] === "cover.jpg")
    ) {
      sourceMembers.push(member);
      continue;
    }
    if (!options.attachEbooks || segments.length < 2) continue;
    const rank = ebookRank(path);
    if (rank === null) continue;
    const directory = segments.slice(0, -1).join("/");
    const previous = preferredByDirectory.get(directory);
    if (!previous || rank < previous.rank)
      preferredByDirectory.set(directory, { member, rank });
  }

  const cap = options.attachmentMaxBytes ?? Number.POSITIVE_INFINITY;
  const preferred = [...preferredByDirectory.values()].map(
    ({ member }) => member,
  );
  const ebooks = preferred.filter((member) => member.file.size <= cap);
  const overCap = preferred.filter((member) => member.file.size > cap);
  const members = [...sourceMembers, ...ebooks];
  const database =
    members.find((member) => member.path === "metadata.db") ?? null;
  return {
    members,
    database,
    covers: sourceMembers.filter((member) => member.path !== "metadata.db")
      .length,
    ebooks,
    ebookBytes: ebooks.reduce((total, member) => total + member.file.size, 0),
    overCap,
    bytes: members.reduce((total, member) => total + member.file.size, 0),
    skipped: files.length - members.length,
  };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const megabytes = bytes / (1024 * 1024);
  return megabytes >= 1
    ? `${megabytes.toFixed(1)} MB`
    : `${Math.round(bytes / 1024)} KB`;
}

/**
 * The members cheap enough to send before knowing whether they are wanted.
 *
 * For Calibre that is `metadata.db` alone: a few hundred kilobytes, always changed
 * because Calibre rewrites it constantly, and the thing the server needs in order to
 * answer at all.
 */
export function cheapMembers(bundle: CalibreBundle): BundleMember[] {
  return bundle.members.filter((member) => member.path === "metadata.db");
}

/** The bundle narrowed to what a plan asked for, keeping the original order. */
export function narrowedTo(
  bundle: CalibreBundle,
  wanted: readonly string[],
): BundleMember[] {
  const keep = new Set(wanted);
  return bundle.members.filter((member) => keep.has(member.path));
}
