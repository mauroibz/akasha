import { useState } from "react";

import type { ImporterDefinition } from "@/api/imports";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * The upload affordance: drop a file on it, or choose one.
 *
 * Both paths land in the same `onFile`, so nothing downstream knows how the file
 * arrived. The file input stays a real, visible input rather than a hidden one
 * behind a styled button — it is the keyboard path and the assistive path, and
 * hiding it to make the drop zone prettier would cost both.
 */
export function SourceDropZone({
  importer,
  inputId,
  file,
  onFile,
}: {
  importer: ImporterDefinition;
  inputId: string;
  file: File | null;
  onFile: (file: File | null) => void;
}) {
  const [over, setOver] = useState(false);
  const { accept, empty_state: emptyState, label } = importer.input;
  return (
    <div
      data-testid={`${importer.id}-drop-zone`}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        const dropped = event.dataTransfer?.files?.[0];
        if (dropped) onFile(dropped);
      }}
      className={cn(
        "rounded-2xl border-2 border-dashed p-5 transition-colors",
        over ? "border-primary bg-primary/5" : "border-border",
      )}
    >
      <Label htmlFor={inputId}>{label}</Label>
      <p className="mt-1 text-sm text-muted-foreground">
        {file ? file.name : (emptyState ?? `Choose a ${label}.`)}
      </p>
      <Input
        id={inputId}
        autoFocus
        className="mt-3 h-11 py-2"
        type="file"
        accept={accept ?? undefined}
        onChange={(event) => onFile(event.target.files?.[0] ?? null)}
      />
      {accept && (
        <p className="mt-2 text-xs text-muted-foreground">
          Accepts {accept.split(",")[0]} files.
        </p>
      )}
    </div>
  );
}
