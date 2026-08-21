import { Folder, FolderOpen } from "lucide-react";
import { useEffect, useState } from "react";

import { browseImportSource, type ImportBrowseListing } from "@/api/imports";
import { Button } from "@/components/ui/button";

/**
 * Where under the connector's mount you are, and what is one level down.
 *
 * "Enter a relative folder only" was the whole of the old guidance, and it is
 * unanswerable: nobody can name a folder inside a mount they cannot see. The
 * backend lists directory names and refuses to leave the mount, so this renders
 * names and never a host path (DEC-079).
 */
export function FolderPicker({
  importerId,
  importerLabel,
  emptyState,
  selected,
  onSelect,
}: {
  importerId: string;
  importerLabel: string;
  emptyState: string | null;
  selected: string;
  onSelect: (path: string) => void;
}) {
  const [at, setAt] = useState("");
  const [listing, setListing] = useState<ImportBrowseListing | null>(null);
  const [failure, setFailure] = useState("");

  useEffect(() => {
    let abandoned = false;
    void browseImportSource(importerId, at)
      .then((next) => {
        if (abandoned) return;
        setListing(next);
        setFailure("");
      })
      .catch((reason: Error) => {
        if (abandoned) return;
        setListing(null);
        setFailure(reason.message);
      });
    return () => {
      abandoned = true;
    };
  }, [importerId, at]);

  const open = (path: string) => {
    setAt(path);
    // Browsing into a folder is also choosing it: the folder you are standing in
    // is the one Preview would read, and making that a second click would be a
    // second thing to explain.
    onSelect(path);
  };

  const trail = at ? at.split("/") : [];
  return (
    <div className="rounded-2xl border border-border">
      <nav
        aria-label={`${importerLabel} folders`}
        className="flex flex-wrap items-center gap-1 border-b border-border px-3 py-2 text-sm"
      >
        <Button
          type="button"
          variant="ghost"
          className="h-8 rounded-lg px-2 text-sm"
          onClick={() => open("")}
        >
          {importerLabel} library root
        </Button>
        {trail.map((segment, index) => (
          <span key={`${segment}-${index}`} className="flex items-center gap-1">
            <span aria-hidden="true" className="text-muted-foreground">
              /
            </span>
            <Button
              type="button"
              variant="ghost"
              className="h-8 rounded-lg px-2 text-sm"
              onClick={() => open(trail.slice(0, index + 1).join("/"))}
            >
              {segment}
            </Button>
          </span>
        ))}
      </nav>
      {failure ? (
        <p className="px-4 py-5 text-sm text-destructive" role="status">
          {failure}
        </p>
      ) : listing === null ? (
        <p className="px-4 py-5 text-sm text-muted-foreground" role="status">
          Reading folders…
        </p>
      ) : (
        <>
          {/* One sentence, derived once. Two independent ones contradicted each
              other in the walkthrough: an empty leaf folder said "open one
              below" directly above "no folders here". */}
          <p
            className={
              listing.importable
                ? "border-b border-border px-4 py-2 text-sm text-score-top"
                : "border-b border-border px-4 py-2 text-sm text-muted-foreground"
            }
          >
            {listing.importable
              ? `This folder holds a ${importerLabel} library.`
              : listing.directories.length > 0
                ? `No ${importerLabel} library in this folder — open one below.`
                : listing.path === ""
                  ? // The connector's own copy for "your source is not mounted",
                    // which is only true at the root. Deeper down, an empty
                    // folder is just an empty folder.
                    (emptyState ?? `No ${importerLabel} library is mounted.`)
                  : `Nothing inside this folder, and no ${importerLabel} library here.`}
          </p>
          {listing.directories.length > 0 && (
            <ul className="max-h-64 overflow-y-auto p-2">
              {listing.directories.map((name) => (
                <li key={name}>
                  <Button
                    type="button"
                    variant="ghost"
                    className="h-10 w-full justify-start gap-2 rounded-lg px-3 text-sm font-normal"
                    onClick={() => open(at ? `${at}/${name}` : name)}
                  >
                    {at && name === selected.split("/").at(-1) ? (
                      <FolderOpen aria-hidden="true" className="h-4 w-4" />
                    ) : (
                      <Folder aria-hidden="true" className="h-4 w-4" />
                    )}
                    {name}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
