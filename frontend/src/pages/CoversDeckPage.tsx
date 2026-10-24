import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";

import {
  chooseCover,
  fetchCoverCandidates,
  fetchProviderCover,
  getLibraryPage,
  type LibraryEntry,
} from "@/api/library";
import { queryKeys } from "@/api/keys";
import { Button } from "@/components/ui/button";
import { coverlessFilters } from "@/features/chores/chores";
import { Deck, DeckEnd, type DeckControls } from "@/features/deck/Deck";
import { titleSize } from "@/features/deck/titleSize";
import { mergeUniqueEntries } from "@/features/library/library";
import { cn } from "@/lib/utils";

/** A candidate's URL, or `provider`: ask the item's own provider for its cover. */
type Draft = { choice: string | null };

/**
 * *Find a cover* (Sprint 112, DEC-176): everything without a cover, one card at a
 * time. The card on screen alone asks for candidates (never a page of them, never
 * while rendering a library page); a domain that chooses no covers asks its own
 * provider instead. Nothing chosen and *Use this cover* does nothing: that is *Later*.
 */
export function CoversDeckPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const queue = useInfiniteQuery({
    queryKey: ["chores", "covers"],
    queryFn: ({ pageParam, signal }) =>
      getLibraryPage(coverlessFilters, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    retry: false,
  });
  const entries = useMemo(
    () => mergeUniqueEntries(queue.data?.pages.map((page) => page.items) ?? []),
    [queue.data],
  );

  return (
    <Deck<LibraryEntry, Draft>
      label="Find a cover"
      progressLabel="Progress through what has no cover"
      closeLabel="Back to Tidy up"
      onClose={() => navigate("/deck")}
      source={{
        cards: entries,
        total: queue.data?.pages[0]?.total ?? 0,
        isPending: queue.isPending,
        isError: queue.isError,
        hasNextPage: queue.hasNextPage,
        isFetchingNextPage: queue.isFetchingNextPage,
        fetchNextPage: () => void queue.fetchNextPage(),
        refetch: () => void queue.refetch(),
      }}
      loadingLabel="Finding what has no cover…"
      errorTitle="The list could not be loaded"
      keyOf={(entry) => entry.id}
      entryOf={(entry) => entry}
      initialDraft={() => ({ choice: null })}
      canFile={(_entry, draft) => draft.choice !== null}
      stamp={() => "Cover"}
      filedNoun="covered"
      failure="The cover could not be installed"
      file={async (entry, draft) => {
        if (draft.choice === "provider")
          await fetchProviderCover(entry.item.id);
        else if (draft.choice) await chooseCover(entry.item.id, draft.choice);
        void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      }}
      // An installed cover stays; the card comes back so another can replace it.
      unfile={async () => undefined}
      renderControls={(entry, controls) => (
        <CoverChoices entry={entry} controls={controls} />
      )}
      renderEnd={({ filed, passedNow, waitingPassed, roundAgain, close }) => (
        <DeckEnd
          entries={filed.map(({ card }) => card)}
          title={waitingPassed ? "That’s the deck" : "Every one has a cover"}
          summary={`${filed.length} covered${
            passedNow ? ` · ${passedNow} left for later` : ""
          }.`}
        >
          {waitingPassed > 0 && (
            <Button className="rounded-full px-5" onClick={roundAgain}>
              Go through the {waitingPassed} you passed
            </Button>
          )}
          <Button
            variant={waitingPassed ? "secondary" : "default"}
            className="rounded-full px-5"
            onClick={close}
          >
            Back to Tidy up
          </Button>
        </DeckEnd>
      )}
    />
  );
}

function CoverChoices({
  entry,
  controls: { draft, setDraft, commit },
}: {
  entry: LibraryEntry;
  controls: DeckControls<Draft>;
}) {
  const candidates = useQuery({
    queryKey: queryKeys.coverCandidates(entry.item.id),
    queryFn: () => fetchCoverCandidates(entry.item.id),
    retry: false,
  });
  // CoverDialog's rule: a candidate that fails to load, or loads as a thumbnail
  // the server would refuse, is dropped rather than offered.
  const [broken, setBroken] = useState<Set<string>>(new Set());
  const drop = (url: string) =>
    setBroken((previous) => new Set(previous).add(url));
  const rows = (candidates.data?.candidates ?? []).filter(
    (row) => !broken.has(row.cover_url),
  );
  const reason = candidates.data?.reason;
  return (
    <section
      aria-label={`A cover for ${entry.item.title}`}
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
      </div>
      {candidates.isPending ? (
        <p className="text-sm text-muted-foreground">Looking for covers…</p>
      ) : rows.length > 0 ? (
        <ul
          aria-label="Covers to choose from"
          className="grid grid-cols-6 gap-2 md:grid-cols-3"
        >
          {rows.slice(0, 6).map((row) => {
            const on = draft.choice === row.cover_url;
            return (
              <li key={row.cover_url}>
                <button
                  type="button"
                  aria-pressed={on}
                  aria-label={
                    row.year
                      ? `The ${row.year} edition's cover`
                      : `A cover from ${row.title}`
                  }
                  onClick={() =>
                    setDraft({ choice: on ? null : row.cover_url })
                  }
                  className={cn(
                    "block aspect-[2/3] w-full overflow-hidden rounded-md ring-2 transition focus-ring",
                    on ? "ring-primary" : "ring-transparent hover:ring-border",
                  )}
                >
                  <img
                    src={row.cover_url}
                    alt=""
                    loading="lazy"
                    className="h-full w-full bg-surface-raised object-cover"
                    onError={() => {
                      drop(row.cover_url);
                      if (draft.choice === row.cover_url)
                        setDraft({ choice: null });
                    }}
                    onLoad={(event) => {
                      const image = event.currentTarget;
                      if (image.naturalWidth < 200 || image.naturalHeight < 200)
                        drop(row.cover_url);
                    }}
                  />
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span>
            {reason === "not_supported"
              ? "This library takes its cover from its provider."
              : "No other editions to choose from."}
          </span>
          <button
            type="button"
            aria-pressed={draft.choice === "provider"}
            onClick={() =>
              setDraft({
                choice: draft.choice === "provider" ? null : "provider",
              })
            }
            className={cn(
              "rounded-full border px-4 py-2 font-medium transition-colors focus-ring",
              draft.choice === "provider"
                ? "border-primary bg-primary/15 text-primary"
                : "border-border hover:bg-accent",
            )}
          >
            Ask the provider for its cover
          </button>
        </div>
      )}
      <div className="grid grid-cols-[1fr_1.6fr] gap-3">
        <Button
          variant="secondary"
          className="h-12 gap-2 rounded-full text-base md:h-14"
          onClick={() => commit("later")}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Later
        </Button>
        <Button
          className="h-12 gap-2 rounded-full text-base md:h-14"
          disabled={draft.choice === null}
          onClick={() => commit("file")}
        >
          Use this cover
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </section>
  );
}
