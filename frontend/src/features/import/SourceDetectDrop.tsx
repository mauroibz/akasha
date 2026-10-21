import { useState } from "react";
import { toast } from "sonner";

import { detectImporters } from "@/api/imports";
import { FilePicker } from "@/components/ui/file-picker";
import { handFiles } from "@/features/import/handoff";
import { cn } from "@/lib/utils";

/**
 * The top of the source grid (Sprint 096, proposal §5.1): drop or choose an export
 * and Akasha works out whose it is (Sprint 095's detection), so the grid below is
 * only for someone who would rather say.
 */
export function SourceDetectDrop({
  onSource,
}: {
  /** Open this importer; its form picks up the handed files. */
  onSource: (importerId: string) => void;
}) {
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);

  const take = async (files: File[]) => {
    if (files.length === 0) return;
    setBusy(true);
    try {
      const detected = await detectImporters(files);
      const first = detected.find((file) => file.matches[0])?.matches[0];
      if (!first) {
        toast.error(
          files.length === 1
            ? `Akasha cannot read ${files[0].name}`
            : "Akasha cannot read those files",
          { description: "Choose its source below if you know it." },
        );
        return;
      }
      const taken = files.filter(
        (_file, index) =>
          detected[index]?.matches[0]?.importer === first.importer,
      );
      handFiles(first.importer, taken);
      onSource(first.importer);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Those files could not be read",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid="source-detect-drop"
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        void take(Array.from(event.dataTransfer?.files ?? []));
      }}
      className={cn(
        "flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-[border-color,background-color,transform] duration-150",
        over ? "scale-[1.01] border-primary bg-primary/10" : "border-border",
      )}
    >
      <p className="font-display text-2xl font-medium">
        {busy ? "Reading…" : "Drop an export here"}
      </p>
      <p className="max-w-lg text-sm text-muted-foreground">
        From Goodreads, Letterboxd, Trakt, IMDb, MyAnimeList or Spotify, a list
        of your own, or EPUBs. Akasha works out which.
      </p>
      <FilePicker
        aria-label="Choose an export"
        buttonLabel="Choose files"
        multiple
        showChosen={false}
        onChange={(event) =>
          void take(Array.from(event.currentTarget.files ?? []))
        }
      />
    </div>
  );
}
