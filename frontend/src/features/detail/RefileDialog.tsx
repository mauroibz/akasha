import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { searchCandidates, type SearchCandidate } from "@/api/add";
import { refileEntry, type LibraryEntry } from "@/api/library";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Loading } from "@/components/ui/skeleton";
import { useItemTypes } from "@/features/library/useItemTypes";
import { cn } from "@/lib/utils";

interface RefileDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entryId: number;
  title: string;
  itemType: string;
  onMoved: (entry: LibraryEntry) => void;
}

/**
 * Move an entry that landed in the wrong library (Sprint 100).
 *
 * The person picks the library, searches its providers by title, and confirms one
 * record: an item's type is never edited, so the move is that library's own record
 * plus your opinion. The search runs on a press, not on typing, so the dialog costs
 * one provider request per question asked.
 */
export function RefileDialog({
  open,
  onOpenChange,
  entryId,
  title,
  itemType,
  onMoved,
}: RefileDialogProps) {
  const itemTypes = useItemTypes(open);
  const targets = (itemTypes.data ?? []).filter((type) => type.id !== itemType);
  const [target, setTarget] = useState("");
  const [query, setQuery] = useState(title);
  const [asked, setAsked] = useState<{ q: string; type: string } | null>(null);
  const [chosen, setChosen] = useState<SearchCandidate | null>(null);
  const targetId = target || targets[0]?.id || "";
  const targetLabel =
    targets.find((type) => type.id === targetId)?.label ?? "another library";

  useEffect(() => {
    if (!open) return;
    setQuery(title);
    setAsked(null);
    setChosen(null);
  }, [open, title]);

  const results = useQuery({
    queryKey: ["refile-search", asked?.type, asked?.q],
    queryFn: ({ signal }) => searchCandidates(asked!.q, asked!.type, signal),
    enabled: open && asked !== null,
    retry: false,
  });
  const move = useMutation({
    mutationFn: (candidate: SearchCandidate) => refileEntry(entryId, candidate),
    onSuccess: (entry) => {
      onOpenChange(false);
      onMoved(entry);
    },
  });

  function search(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim() || !targetId) return;
    setChosen(null);
    setAsked({ q: query.trim(), type: targetId });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Move to another library</DialogTitle>
          <DialogDescription>
            Find {title} in the library it belongs in. Your status, score,
            notes, dates and shelves come with it; anything that library does
            not have is left behind.
          </DialogDescription>
        </DialogHeader>
        <form className="flex flex-col gap-3" onSubmit={search}>
          <label htmlFor="refile-target" className="text-sm font-medium">
            Move to
          </label>
          <NativeSelect
            id="refile-target"
            value={targetId}
            onChange={(event) => {
              setTarget(event.target.value);
              setAsked(null);
              setChosen(null);
            }}
          >
            {targets.map((type) => (
              <option key={type.id} value={type.id}>
                {type.label}
              </option>
            ))}
          </NativeSelect>
          <div className="flex gap-2">
            <Input
              aria-label="Title to search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <Button type="submit" variant="outline" disabled={!query.trim()}>
              Search
            </Button>
          </div>
        </form>
        {results.isFetching && <Loading label="Searching…" shape="list" />}
        {results.isError && (
          <p className="text-sm text-destructive">
            {results.error instanceof Error
              ? results.error.message
              : "The search failed"}
          </p>
        )}
        {results.data && results.data.items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Nothing in {targetLabel} matches that. Try the title it goes by
            there.
          </p>
        )}
        {results.data && results.data.items.length > 0 && (
          <div
            role="radiogroup"
            aria-label="Matches"
            className="flex max-h-72 flex-col gap-1 overflow-y-auto"
          >
            {results.data.items.map((candidate) => {
              const key = `${candidate.source}:${candidate.source_id}`;
              const selected =
                chosen !== null &&
                `${chosen.source}:${chosen.source_id}` === key;
              return (
                <button
                  key={key}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setChosen(candidate)}
                  className={cn(
                    "flex min-h-11 flex-col items-start rounded-md px-3 py-2 text-left hover:bg-muted focus-ring",
                    selected && "bg-primary/15 text-primary",
                  )}
                >
                  <span className="font-medium">{candidate.title}</span>
                  <span className="text-sm text-muted-foreground">
                    {[candidate.credit ?? candidate.creators[0], candidate.year]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </button>
              );
            })}
          </div>
        )}
        {move.isError && (
          <p role="alert" className="text-sm text-destructive">
            {move.error instanceof Error
              ? move.error.message
              : "The entry could not be moved"}
          </p>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={chosen === null || move.isPending}
            onClick={() => chosen && move.mutate(chosen)}
          >
            Move to {targetLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
