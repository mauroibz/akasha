import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { fetchCoverCandidates, type LibraryItem } from "@/api/library";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface CoverDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: LibraryItem;
  onChoose: (coverUrl: string) => Promise<void>;
}

const reasons: Record<string, string> = {
  no_provider_reference:
    "This book has no provider reference or ISBN, so there is nothing to look editions up by.",
  no_candidates:
    "Open Library lists no other editions with covers for this book.",
  provider_unavailable:
    "Open Library could not be reached. Nothing was changed.",
  provider_disabled: "The Open Library provider is not enabled.",
};

export function CoverDialog({
  open,
  onOpenChange,
  item,
  onChoose,
}: CoverDialogProps) {
  const [chooseError, setChooseError] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  // Only ever fetched while the dialog is open, which is what keeps a library page
  // free of provider traffic.
  const candidates = useQuery({
    queryKey: ["cover-candidates", item.id],
    queryFn: () => fetchCoverCandidates(item.id),
    enabled: open,
    staleTime: 5 * 60 * 1000,
  });

  async function choose(coverUrl: string) {
    setChooseError("");
    setPending(coverUrl);
    try {
      await onChoose(coverUrl);
      onOpenChange(false);
    } catch (error) {
      setChooseError(
        error instanceof Error ? error.message : "Cover could not be changed",
      );
    } finally {
      setPending(null);
    }
  }

  const rows = candidates.data?.candidates ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Choose a cover</DialogTitle>
          <DialogDescription>
            Other editions of {item.title}. Your current cover stays until you
            pick one.
          </DialogDescription>
        </DialogHeader>

        {candidates.isPending && open && (
          <p className="text-sm text-muted-foreground">Loading editions…</p>
        )}
        {candidates.isError && (
          <p className="text-sm text-destructive">
            Cover options could not be loaded. Nothing was changed.
          </p>
        )}
        {candidates.data && rows.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {reasons[candidates.data.reason ?? ""] ??
              "No other editions are available."}
          </p>
        )}
        {chooseError && (
          <p className="text-sm text-destructive">{chooseError}</p>
        )}

        {rows.length > 0 && (
          <ul className="grid max-h-[60vh] grid-cols-3 gap-4 overflow-y-auto sm:grid-cols-4">
            {rows.map((candidate) => (
              <li key={candidate.source_id}>
                <button
                  type="button"
                  disabled={pending !== null}
                  onClick={() => void choose(candidate.cover_url)}
                  className="group w-full rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
                  aria-label={`Use the ${
                    candidate.year ? `${candidate.year} ` : ""
                  }edition cover`}
                >
                  <img
                    className="aspect-[2/3] w-full rounded-lg bg-surface-raised object-cover"
                    src={candidate.cover_url}
                    alt=""
                    loading="lazy"
                    // A candidate cover can 404; a torn-image icon reads as breakage,
                    // so the tile simply goes quiet instead.
                    onError={(event) => {
                      event.currentTarget.style.visibility = "hidden";
                    }}
                  />
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {pending === candidate.cover_url
                      ? "Saving…"
                      : (candidate.year ?? "Year unknown")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
