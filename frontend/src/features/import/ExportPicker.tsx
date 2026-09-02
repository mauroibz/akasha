import { useRef, useState } from "react";

import type { ImportInputSpec } from "@/api/imports";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { formatBytes } from "./bundle";

/**
 * Drop the files a source's own "export everything" feature produced.
 *
 * Unlike `DirectoryPicker`, this is a flat set of opaque files, not a tree to filter:
 * every file the reader offers travels exactly as named, with no relative-path
 * reshaping. Unlike `SourceDropZone`, it takes more than one file at once — the
 * export is incomplete without every part it produced. Nothing here inspects file
 * contents; only the server can tell whether what arrived is actually a complete,
 * readable export.
 */
export function ExportPicker({
  spec,
  inputId,
  files,
  onFiles,
}: {
  spec: ImportInputSpec;
  inputId: string;
  files: File[];
  onFiles: (files: File[]) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  const unexpected = files.filter(
    (file) => !file.name.toLowerCase().endsWith(".calibre-data"),
  );

  const choose = (list: FileList | null) => {
    onFiles(list ? Array.from(list) : []);
  };

  return (
    <div
      data-testid="calibre-export-drop-zone"
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        if (event.dataTransfer?.files?.length) choose(event.dataTransfer.files);
      }}
      className={cn(
        "rounded-2xl border-2 border-dashed p-5 transition-colors",
        over ? "border-primary bg-primary/5" : "border-border",
      )}
    >
      <Label htmlFor={inputId}>{spec.label}</Label>
      <p className="mt-1 text-sm text-muted-foreground">
        {files.length === 0
          ? (spec.empty_state ?? `Choose the ${spec.label} files.`)
          : `${files.length} ${files.length === 1 ? "file" : "files"} selected · ${formatBytes(totalBytes)}`}
      </p>
      <input
        ref={input}
        id={inputId}
        type="file"
        multiple
        accept=".calibre-data"
        className="mt-3 block w-full text-sm file:mr-3 file:h-9 file:rounded-full file:border-0 file:bg-secondary file:px-4 file:text-sm file:font-medium"
        onChange={(event) => choose(event.target.files)}
      />
      {unexpected.length > 0 && (
        <p className="mt-2 text-sm text-destructive" role="status">
          {unexpected.length === 1 ? "This file doesn't" : "These files don't"}{" "}
          look like part of a Calibre export:{" "}
          {unexpected.map((file) => file.name).join(", ")}.
        </p>
      )}
      {files.length > 0 && (
        <Button
          type="button"
          variant="ghost"
          className="mt-2 h-8 rounded-lg px-2 text-sm"
          onClick={() => {
            if (input.current) input.current.value = "";
            onFiles([]);
          }}
        >
          Choose different files
        </Button>
      )}
    </div>
  );
}
