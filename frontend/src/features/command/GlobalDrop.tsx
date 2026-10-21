import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { detectImporters } from "@/api/imports";
import { handFiles } from "@/features/import/handoff";

/**
 * Drop a file anywhere (Sprint 095, proposal §4.2): a veil says so while a file is
 * over the window, and a drop nobody else took is read for what it is and handed to
 * its importer, which previews it at once (Sprint 086's hand-off). The veil does not
 * take pointer events, so every existing drop zone still receives its own drops; a
 * drop it handled arrives here already `defaultPrevented` and is left alone.
 */
export function GlobalDrop() {
  const navigate = useNavigate();
  const [over, setOver] = useState(false);
  const depth = useRef(0);

  useEffect(() => {
    const carriesFiles = (event: DragEvent) =>
      Array.from(event.dataTransfer?.types ?? []).includes("Files");

    const onEnter = (event: DragEvent) => {
      if (!carriesFiles(event)) return;
      depth.current += 1;
      setOver(true);
    };
    const onLeave = (event: DragEvent) => {
      if (!carriesFiles(event)) return;
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setOver(false);
    };
    const onOver = (event: DragEvent) => {
      if (carriesFiles(event)) event.preventDefault();
    };
    const onDrop = (event: DragEvent) => {
      depth.current = 0;
      setOver(false);
      if (event.defaultPrevented || !carriesFiles(event)) return;
      event.preventDefault();
      const files = Array.from(event.dataTransfer?.files ?? []);
      if (files.length > 0) void route(files);
    };

    const route = async (files: File[]) => {
      let detected;
      try {
        detected = await detectImporters(files);
      } catch (error) {
        toast.error(
          error instanceof Error
            ? error.message
            : "Those files could not be read",
        );
        return;
      }
      const claimed = detected
        .map((file, index) => ({
          file: files[index],
          importer: file.matches[0]?.importer,
        }))
        .filter((row): row is { file: File; importer: string } =>
          Boolean(row.importer),
        );
      if (claimed.length === 0) {
        toast.error(
          files.length === 1
            ? `Akasha cannot read ${files[0].name}`
            : "Akasha cannot read any of those files",
          {
            description:
              "Exports from Goodreads, IMDb, Letterboxd, Trakt, Spotify, MyAnimeList, EPUBs and tables are.",
          },
        );
        return;
      }
      // One import at a time: the first claimed file's importer takes every file it
      // claimed (several EPUBs go together); anything else is named, not dropped silently.
      const importer = claimed[0].importer;
      const taken = claimed
        .filter((row) => row.importer === importer)
        .map((row) => row.file);
      const left = files.length - taken.length;
      handFiles(importer, taken);
      navigate(`/import?tab=${importer}`);
      if (left > 0)
        toast(`${left} other file${left === 1 ? "" : "s"} not opened`, {
          description: "Drop them again after this import.",
        });
    };

    window.addEventListener("dragenter", onEnter);
    window.addEventListener("dragleave", onLeave);
    window.addEventListener("dragover", onOver);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragenter", onEnter);
      window.removeEventListener("dragleave", onLeave);
      window.removeEventListener("dragover", onOver);
      window.removeEventListener("drop", onDrop);
    };
  }, [navigate]);

  if (!over) return null;
  return (
    <div
      aria-hidden="true"
      data-testid="drop-veil"
      className="pointer-events-none fixed inset-3 z-[70] flex items-center justify-center rounded-3xl border-2 border-dashed border-primary bg-background/80 backdrop-blur-sm"
    >
      <div className="flex flex-col items-center gap-3 text-center">
        <svg
          width="56"
          height="56"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.6}
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M4 21V10a8 8 0 0 1 16 0v11" />
          <circle
            cx="12"
            cy="11"
            r="2"
            fill="#fbbf24"
            stroke="none"
            className="origin-[12px_11px] animate-breathe [transform-box:view-box]"
          />
        </svg>
        <p className="font-display text-3xl font-medium">Drop to add</p>
        <p className="text-sm text-muted-foreground">
          Exports, lists and EPUBs: Akasha works out which.
        </p>
      </div>
    </div>
  );
}
