import { describe, expect, it } from "vitest";

import { calibreBundle, cheapMembers, formatBytes, narrowedTo } from "./bundle";

/** A File carrying the relative path a directory pick would give it. */
function pick(path: string, size = 1024): File {
  const file = new File([new Uint8Array(size)], path.split("/").pop() ?? path);
  Object.defineProperty(file, "webkitRelativePath", { value: path });
  return file;
}

describe("calibreBundle", () => {
  it("keeps the database and the covers and drops everything else", () => {
    // The exact shape of the owner's library, including the trash cover that a
    // `cover.jpg` glob would have uploaded (DEC-081).
    const bundle = calibreBundle([
      pick("Calibre Library/metadata.db", 416 * 1024),
      pick("Calibre Library/metadata_db_prefs_backup.json"),
      pick(
        "Calibre Library/Brandon Sanderson/Mistborn_ The Final Empire (2)/cover.jpg",
        1200,
      ),
      pick(
        "Calibre Library/Brandon Sanderson/Mistborn_ The Final Empire (2)/metadata.opf",
      ),
      pick(
        "Calibre Library/Brandon Sanderson/Mistborn_ The Final Empire (2)/book.epub",
        9_000_000,
      ),
      pick("Calibre Library/.caltrash/b/1/cover.jpg"),
      pick("Calibre Library/.calnotes/notes.db"),
    ]);

    expect(bundle.members.map((member) => member.path)).toEqual([
      "metadata.db",
      "Brandon Sanderson/Mistborn_ The Final Empire (2)/cover.jpg",
    ]);
    expect(bundle.covers).toBe(1);
    expect(bundle.skipped).toBe(5);
    // The 9 MB ebook is not in the total; that is the whole point.
    expect(bundle.bytes).toBe(416 * 1024 + 1200);
  });

  it("strips the picked folder's own name from every path", () => {
    // The reader's folder may be called anything; the library's shape is what the
    // server sees, so `metadata.db` has to land at the root.
    const bundle = calibreBundle([pick("whatever-i-called-it/metadata.db")]);
    expect(bundle.database?.path).toBe("metadata.db");
  });

  it("reports no database when the reader picked the wrong folder", () => {
    const bundle = calibreBundle([pick("Books/Author/Book (1)/cover.jpg")]);
    expect(bundle.database).toBeNull();
  });

  it("does not mistake a nested metadata.db for the library's own", () => {
    const bundle = calibreBundle([pick("Lib/Author/metadata.db")]);
    expect(bundle.database).toBeNull();
    expect(bundle.members).toHaveLength(0);
  });
});

describe("formatBytes", () => {
  it("reads as a size a person would say out loud", () => {
    expect(formatBytes(900)).toBe("900 B");
    expect(formatBytes(416 * 1024)).toBe("416 KB");
    expect(formatBytes(2_516_582)).toBe("2.4 MB");
  });
});

describe("planning helpers", () => {
  const bundle = calibreBundle([
    pick("Lib/metadata.db", 416 * 1024),
    pick("Lib/A/One (1)/cover.jpg", 1000),
    pick("Lib/B/Two (2)/cover.jpg", 2000),
  ]);

  it("sends only the database while asking what is wanted", () => {
    // Cheap, always changed, and the only thing the server can answer from.
    expect(cheapMembers(bundle).map((m) => m.path)).toEqual(["metadata.db"]);
  });

  it("narrows the bundle to what the plan asked for", () => {
    const narrowed = narrowedTo(bundle, ["metadata.db", "B/Two (2)/cover.jpg"]);
    expect(narrowed.map((m) => m.path)).toEqual([
      "metadata.db",
      "B/Two (2)/cover.jpg",
    ]);
  });

  it("ignores a path the plan names that the bundle does not hold", () => {
    expect(narrowedTo(bundle, ["nonsense.jpg"])).toEqual([]);
  });
});
