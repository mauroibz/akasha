import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import { putMedia, type Media, type Medium, type Presence } from "@/api/media";
import { cn } from "@/lib/utils";

import { useMedia } from "./useMedia";

const presences: Array<{ value: Presence; label: string; says: string }> = [
  { value: "front", label: "Front", says: "in front" },
  { value: "kept", label: "Kept", says: "kept" },
  { value: "off", label: "Off", says: "off" },
];

/**
 * Your media (Sprint 143, DEC-193): the order the application lists them in, and
 * what each is to the person. *Front* media feed the front of the Library: what is
 * under way, what happened lately, what is next. *Kept* media are in the library
 * and its choosers. *Off* media are shown nowhere; nothing is deleted.
 *
 * Every change is stored at once, as arranging the showcases is. A row moves with
 * its two arrows, which is also the keyboard's way; the focus follows the row.
 */
export function YourMedia({
  title = "Your media",
  heading = true,
  className,
}: {
  title?: string;
  /** Off where the screen already titles the section (Settings). */
  heading?: boolean;
  className?: string;
}) {
  const queryClient = useQueryClient();
  const media = useMedia();
  const [announcement, setAnnouncement] = useState("");
  const save = useMutation({
    mutationFn: putMedia,
    // One at a time, in the order made, so quick changes are stored as the last.
    scope: { id: "media" },
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.media, saved);
      // The front of the Library is of the media in front.
      void queryClient.invalidateQueries({ queryKey: queryKeys.home });
      void queryClient.invalidateQueries({ queryKey: queryKeys.homeLayout });
    },
    onError: (error) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.media });
      toast.error(
        error instanceof Error
          ? error.message
          : "Your media could not be saved",
      );
    },
  });
  const rows = Array.isArray(media.data?.media) ? media.data.media : [];
  if (rows.length === 0) return null;

  const commit = (next: Medium[]) => {
    // Shown at once; the request follows in the background.
    queryClient.setQueryData<Media>(queryKeys.media, {
      media: next,
      chosen: true,
    });
    save.mutate(
      next.map((row) => ({ item_type: row.item_type, presence: row.presence })),
    );
  };
  const move = (index: number, step: number) => {
    const to = index + step;
    if (to < 0 || to >= rows.length) return;
    const next = [...rows];
    [next[index], next[to]] = [next[to], next[index]];
    commit(next);
    setAnnouncement(
      `${rows[index].label} moved to ${to + 1} of ${rows.length}`,
    );
  };
  const set = (index: number, presence: Presence) => {
    commit(rows.map((row, at) => (at === index ? { ...row, presence } : row)));
    setAnnouncement(
      `${rows[index].label} ${presences.find((p) => p.value === presence)?.says}`,
    );
  };

  return (
    <section aria-label={title} className={className}>
      {heading && <h3 className="font-display text-lg font-medium">{title}</h3>}
      <p className="mt-1 max-w-prose text-sm text-muted-foreground">
        The order is the order everywhere. Front media fill Now and Lately; kept
        media stay in the library; off media are hidden and nothing is deleted.
      </p>
      <ol className="mt-3 space-y-1.5">
        {rows.map((row, index) => (
          <li
            key={row.item_type}
            data-medium={row.item_type}
            className={cn(
              "flex min-h-12 flex-wrap items-center gap-2 rounded-lg border border-border bg-surface px-2 py-1.5",
              row.presence === "off" && "text-muted-foreground",
            )}
          >
            <span className="flex shrink-0">
              <button
                type="button"
                aria-label={`Move ${row.label} earlier`}
                disabled={index === 0}
                onClick={() => move(index, -1)}
                className="flex h-11 w-9 items-center justify-center rounded-md text-muted-foreground hover:text-foreground focus-ring disabled:opacity-30"
              >
                <ArrowUp className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label={`Move ${row.label} later`}
                disabled={index === rows.length - 1}
                onClick={() => move(index, 1)}
                className="flex h-11 w-9 items-center justify-center rounded-md text-muted-foreground hover:text-foreground focus-ring disabled:opacity-30"
              >
                <ArrowDown className="h-4 w-4" aria-hidden="true" />
              </button>
            </span>
            <span className="min-w-0 flex-1 truncate font-medium">
              {row.label}
              {!row.held && (
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  nothing yet
                </span>
              )}
            </span>
            <span
              role="radiogroup"
              aria-label={`${row.label} are`}
              className="flex shrink-0 rounded-full bg-muted p-0.5"
            >
              {presences.map((presence) => (
                <button
                  key={presence.value}
                  type="button"
                  role="radio"
                  aria-checked={row.presence === presence.value}
                  onClick={() => set(index, presence.value)}
                  className="min-h-10 rounded-full px-3 text-xs font-medium text-muted-foreground focus-ring aria-checked:bg-surface-raised aria-checked:text-foreground"
                >
                  {presence.label}
                </button>
              ))}
            </span>
          </li>
        ))}
      </ol>
      <p role="status" className="sr-only">
        {announcement}
      </p>
    </section>
  );
}

/**
 * The first screen's one question (Sprint 143): "What do you keep?", asked of
 * someone who holds nothing and has not chosen. It stays for the visit once shown,
 * so answering it does not take it away after the first tap.
 */
export function WhatDoYouKeep({ className }: { className?: string }) {
  const media = useMedia();
  const [asked, setAsked] = useState(false);
  const rows = Array.isArray(media.data?.media) ? media.data.media : [];
  const asks =
    rows.length > 1 &&
    media.data?.chosen === false &&
    rows.every((row) => !row.held);
  if (asks && !asked) setAsked(true);
  if (!asked) return null;
  return <YourMedia title="What do you keep?" className={className} />;
}
