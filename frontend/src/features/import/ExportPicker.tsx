import { useRef, useState } from "react";

import type { ImportInputSpec } from "@/api/imports";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { formatBytes } from "./bundle";
import { FilePicker } from "@/components/ui/file-picker";

/**
 * Drop a flat set of files: a source's own export parts, or files that each
 * describe themselves (Sprint 086's EPUBs).
 *
 * Unlike `DirectoryPicker`, this is a flat set of opaque files, not a tree to filter:
 * every file the reader offers travels exactly as named, with no relative-path
 * reshaping. Unlike `SourceDropZone`, it takes more than one file at once. What it
 * accepts is the connector's declaration, never a name this component knows — the
 * server refuses an undeclared member anyway; this only says so before the upload.
 */
export function ExportPicker({
  importerId,
  spec,
  inputId,
  files,
  onFiles,
}: {
  importerId: string;
  spec: ImportInputSpec;
  inputId: string;
  files: File[];
  onFiles: (files: File[]) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  const extensions = (spec.accept ?? "")
    .split(",")
    .map((part) => part.trim().toLowerCase())
    .filter((part) => part.startsWith("."));
  const unexpected = extensions.length
    ? files.filter(
        (file) =>
          !extensions.some((extension) =>
            file.name.toLowerCase().endsWith(extension),
          ),
      )
    : [];

  const choose = (list: FileList | null) => {
    onFiles(list ? Array.from(list) : []);
  };

  return (
    <div
      data-testid={`${importerId}-export-drop-zone`}
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
      <FilePicker
        ref={input}
        id={inputId}
        multiple
        buttonLabel="Choose files"
        showChosen={false}
        accept={spec.accept ?? undefined}
        className="mt-3"
        onChange={(event) => choose(event.target.files)}
      />
      {unexpected.length > 0 && (
        <p className="mt-2 text-sm text-destructive" role="status">
          {unexpected.length === 1 ? "This file isn't" : "These files aren't"}{" "}
          one {spec.label} accepts:{" "}
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
