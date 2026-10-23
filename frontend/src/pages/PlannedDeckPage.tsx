import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, X } from "lucide-react";

import {
  bulkDeleteEntries,
  getLibraryPage,
  type LibraryEntry,
} from "@/api/library";
import { queryKeys } from "@/api/keys";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { plannedFilters } from "@/features/chores/chores";
import { Deck, DeckEnd } from "@/features/deck/Deck";
import { titleSize } from "@/features/deck/titleSize";
import { howLong } from "@/features/house/house";
import { statusLabelFor } from "@/features/library/labels";
import { mergeUniqueEntries } from "@/features/library/library";
import { useItemTypes } from "@/features/library/useItemTypes";
import { cn } from "@/lib/utils";

type Draft = { letGo: boolean };

/**
 * *Still want this?* (Sprint 112, DEC-176): the planned pile one card at a time,
 * what has waited longest first. *Keep* and *Later* write nothing. *Let go* only
 * marks the card; the end of the round asks once before removing them, so nothing
 * is deleted card by card and an undo before then costs nothing.
 */
export function PlannedDeckPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const itemTypes = useItemTypes();
  const filters = useMemo(
    () => plannedFilters(itemTypes.data),
    [itemTypes.data],
  );
  const ready = itemTypes.isSuccess && filters.statuses.length > 0;

  const pile = useInfiniteQuery({
    queryKey: ["chores", "planned", filters],
    queryFn: ({ pageParam, signal }) =>
      getLibraryPage(filters, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: ready,
    retry: false,
  });
  const entries = useMemo(
    () => mergeUniqueEntries(pile.data?.pages.map((page) => page.items) ?? []),
    [pile.data],
  );

  const [confirming, setConfirming] = useState<LibraryEntry[] | null>(null);
  const [removed, setRemoved] = useState<number | null>(null);
  const remove = useMutation({
    mutationFn: (ids: number[]) => bulkDeleteEntries({ entry_ids: ids }),
    onSuccess: (affected) => {
      setRemoved(affected);
      setConfirming(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      void queryClient.invalidateQueries({ queryKey: ["chores"] });
    },
  });
  const close = () => navigate("/deck");

  return (
    <>
      <Deck<LibraryEntry, Draft>
        label="Still want this?"
        progressLabel="Progress through the planned pile"
        closeLabel="Back to the chores"
        onClose={close}
        source={{
          cards: entries,
          total: pile.data?.pages[0]?.total ?? 0,
          isPending: !ready || pile.isPending,
          isError: pile.isError,
          hasNextPage: pile.hasNextPage,
          isFetchingNextPage: pile.isFetchingNextPage,
          fetchNextPage: () => void pile.fetchNextPage(),
          refetch: () => void pile.refetch(),
        }}
        loadingLabel="Gathering the pile…"
        errorTitle="The planned pile could not be loaded"
        keyOf={(entry) => entry.id}
        entryOf={(entry) => entry}
        initialDraft={() => ({ letGo: false })}
        stamp={(_entry, draft) => (draft.letGo ? "Let go" : "Keep")}
        filedNoun="decided"
        file={async () => undefined}
        unfile={async () => undefined}
        onKey={(event, _entry, { commit }) => {
          if (event.key === "x") {
            commit("file", { letGo: true });
            return true;
          }
          return false;
        }}
        renderControls={(entry, { commit }) => (
          <section
            aria-label={`Decide on ${entry.item.title}`}
            className="flex shrink-0 flex-col gap-3 md:justify-center md:gap-6"
          >
            <div className="text-center md:text-left">
              <h2
                className={cn(
                  "line-clamp-4 font-display font-medium leading-tight tracking-tight",
                  titleSize(entry.item.title),
                )}
                data-testid="deck-title"
              >
                {entry.item.title}
              </h2>
              <p className="mt-1 truncate text-sm text-muted-foreground md:mt-3 md:text-base">
                {entry.item.creator ?? "Unknown"}
                {entry.item.year !== null && ` · ${entry.item.year}`}
              </p>
              <p className="mt-2 text-sm text-muted-foreground md:text-base">
                {statusLabelFor(entry.item.type, itemTypes.data, entry.status)}{" "}
                for{" "}
                {howLong(entry.date_added.slice(0, 10), new Date()).replace(
                  "since today",
                  "a day",
                )}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Button
                variant="secondary"
                className="h-12 gap-2 rounded-full text-base md:h-14"
                onClick={() => commit("later")}
              >
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                Later
              </Button>
              <Button
                variant="outline"
                className="h-12 gap-2 rounded-full border-destructive/60 text-base text-destructive hover:bg-destructive/10 hover:text-destructive md:h-14"
                onClick={() => commit("file", { letGo: true })}
              >
                <X className="h-4 w-4" aria-hidden="true" />
                Let go
              </Button>
              <Button
                className="h-12 gap-2 rounded-full text-base md:h-14"
                onClick={() => commit("file", { letGo: false })}
              >
                Keep
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
            <p className="hidden text-xs text-muted-foreground md:block">
              <kbd>→</kbd> keep · <kbd>x</kbd> let go · <kbd>←</kbd> later ·{" "}
              <kbd>Backspace</kbd> undo · <kbd>Esc</kbd> leave. Nothing is
              removed until the end, and only after you say so.
            </p>
          </section>
        )}
        renderEnd={({ filed, passedNow, close: leave }) => {
          const letGo = filed
            .filter(({ draft }) => draft.letGo)
            .map(({ card }) => card);
          const kept = filed.length - letGo.length;
          if (removed !== null)
            return (
              <DeckEnd
                entries={[]}
                title="The pile is lighter"
                summary={`Removed ${removed} · ${kept} kept.`}
              >
                <Button className="rounded-full px-5" onClick={leave}>
                  Back to the chores
                </Button>
              </DeckEnd>
            );
          return (
            <DeckEnd
              entries={filed
                .filter(({ draft }) => !draft.letGo)
                .map(({ card }) => card)}
              title={letGo.length ? "Let go of these?" : "The pile is sorted"}
              summary={[
                `${kept} kept`,
                letGo.length ? `${letGo.length} to let go` : null,
                passedNow ? `${passedNow} left for later` : null,
              ]
                .filter(Boolean)
                .join(" · ")
                .concat(".")}
            >
              {letGo.length > 0 && (
                <Button
                  variant="destructive"
                  className="rounded-full px-5"
                  onClick={() => setConfirming(letGo)}
                >
                  Remove the {letGo.length} you let go
                </Button>
              )}
              <Button
                variant={letGo.length ? "secondary" : "default"}
                className="rounded-full px-5"
                onClick={leave}
              >
                {letGo.length ? "Keep them all" : "Back to the chores"}
              </Button>
            </DeckEnd>
          );
        }}
      />
      <AlertDialog
        open={confirming !== null}
        onOpenChange={(open) => !open && setConfirming(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Remove {confirming?.length} from your library?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirming?.map((entry) => entry.item.title).join(", ")}. Their
              status, notes and shelves go with them.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {remove.error && (
            <p role="alert" className="text-sm text-destructive">
              {remove.error.message}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(
                buttonVariants({ variant: "destructive" }),
                "rounded-full px-5",
              )}
              onClick={(event) => {
                event.preventDefault();
                if (confirming)
                  remove.mutate(confirming.map((entry) => entry.id));
              }}
            >
              Remove {confirming?.length}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
