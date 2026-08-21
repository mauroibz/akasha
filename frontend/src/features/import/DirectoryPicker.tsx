import { useRef, useState } from "react";

import type { ImportInputSpec } from "@/api/imports";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { calibreBundle, formatBytes, type CalibreBundle } from "./bundle";

/**
 * Choose a library folder on your own machine.
 *
 * The browser reads the folder directly, so there is nothing to mount, nothing to
 * configure and no restart — and nothing holds the library open while another
 * program is using it (DEC-081). Only the database and the covers are uploaded;
 * the summary says so before anything is sent, because "choose a folder" and
 * "upload 32 MB of ebooks" would otherwise be indistinguishable to the reader.
 */
export function DirectoryPicker({
  spec,
  importerLabel,
  inputId,
  bundle,
  onBundle,
  attachmentMaxBytes,
}: {
  spec: ImportInputSpec;
  importerLabel: string;
  inputId: string;
  bundle: CalibreBundle | null;
  onBundle: (bundle: CalibreBundle | null) => void;
  attachmentMaxBytes: number;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [chosen, setChosen] = useState("");
  const [files, setFiles] = useState<readonly File[]>([]);
  const [attachEbooks, setAttachEbooks] = useState(false);
  const sourceBytes = bundle ? bundle.bytes - bundle.ebookBytes : 0;
  const overCap =
    bundle !== null && spec.max_bytes !== null && sourceBytes > spec.max_bytes;

  const buildBundle = (selected: readonly File[], includeEbooks: boolean) =>
    calibreBundle(selected, {
      attachEbooks: includeEbooks,
      attachmentMaxBytes,
    });

  return (
    <div className="rounded-2xl border-2 border-dashed border-border p-5">
      <Label htmlFor={inputId}>{spec.label}</Label>
      <p className="mt-1 text-sm text-muted-foreground">
        {chosen || (spec.empty_state ?? `Choose your ${importerLabel} folder.`)}
      </p>
      <input
        ref={input}
        id={inputId}
        type="file"
        multiple
        // Not in the HTML standard proper, but present in every current browser and
        // the only way to read a folder without a mount. React does not know the
        // attribute, hence the cast; a browser without it leaves the alternate below.
        {...({ webkitdirectory: "" } as Record<string, string>)}
        className="mt-3 block w-full text-sm file:mr-3 file:h-9 file:rounded-full file:border-0 file:bg-secondary file:px-4 file:text-sm file:font-medium"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length === 0) {
            setChosen("");
            setFiles([]);
            onBundle(null);
            return;
          }
          const first = files[0].webkitRelativePath || files[0].name;
          setChosen(first.split("/")[0]);
          setFiles(files);
          onBundle(buildBundle(files, attachEbooks));
        }}
      />
      <div className="mt-4 flex items-start gap-2">
        <Checkbox
          id={`${inputId}-ebooks`}
          checked={attachEbooks}
          onCheckedChange={(checked) => {
            const enabled = checked === true;
            setAttachEbooks(enabled);
            if (files.length > 0) onBundle(buildBundle(files, enabled));
          }}
        />
        <div>
          <Label htmlFor={`${inputId}-ebooks`}>
            Also attach the ebook files
          </Label>
          <p className="mt-1 text-xs text-muted-foreground">
            One file per book, preferring epub. Files are attached only after
            you commit the preview.
          </p>
        </div>
      </div>
      {bundle && (
        <div
          className="mt-3 rounded-xl bg-surface-raised p-3 text-sm"
          role="status"
        >
          {bundle.database === null ? (
            // Refused here rather than by the server: the reader picked the wrong
            // folder, and a round trip would not tell them anything new.
            <p className="text-destructive">
              That folder holds no metadata.db, so it is not a {importerLabel}{" "}
              library. Choose the folder that contains it.
            </p>
          ) : overCap ? (
            <p className="text-destructive">
              That library is {formatBytes(sourceBytes)}, over the{" "}
              {formatBytes(spec.max_bytes ?? 0)} this accepts. Use the mounted
              path below instead.
            </p>
          ) : (
            <>
              <p className="text-foreground">
                Sending metadata.db and {bundle.covers}{" "}
                {bundle.covers === 1 ? "cover" : "covers"} ·{" "}
                {formatBytes(sourceBytes)}
              </p>
              {attachEbooks && bundle.ebooks.length > 0 && (
                <p className="mt-1 text-foreground">
                  Attaching {bundle.ebooks.length}{" "}
                  {bundle.ebooks.length === 1 ? "ebook" : "ebooks"} after commit
                  · {formatBytes(bundle.ebookBytes)}
                </p>
              )}
              {bundle.skipped > 0 && (
                <p className="mt-1 text-muted-foreground">
                  {bundle.skipped} other{" "}
                  {bundle.skipped === 1 ? "file stays" : "files stay"} on your
                  machine
                  {!attachEbooks && " — your ebooks are never uploaded"}.
                </p>
              )}
              {bundle.overCap.length > 0 && (
                <div className="mt-2 text-destructive">
                  <p>
                    Too large to attach ({formatBytes(attachmentMaxBytes)} per
                    file):
                  </p>
                  <ul className="mt-1 list-disc pl-5">
                    {bundle.overCap.map((member) => (
                      <li key={member.path}>
                        {member.path} · {formatBytes(member.file.size)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
      {chosen && (
        <Button
          type="button"
          variant="ghost"
          className="mt-2 h-8 rounded-lg px-2 text-sm"
          onClick={() => {
            if (input.current) input.current.value = "";
            setChosen("");
            setFiles([]);
            onBundle(null);
          }}
        >
          Choose a different folder
        </Button>
      )}
    </div>
  );
}
