import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { getRevisit, patchEntry, type RevisitCard } from "@/api/library";
import { queryKeys } from "@/api/keys";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Deck, DeckEnd, type DeckControls } from "@/features/deck/Deck";
import { titleSize } from "@/features/deck/titleSize";
import { scoreArticle } from "@/features/rescore/rescore";
import { scoreChipClass } from "@/lib/score";
import { cn } from "@/lib/utils";

type Draft = { score: number; reason: "reread" | "time"; note: string };

const WHEN = new Intl.DateTimeFormat(undefined, {
  month: "long",
  year: "numeric",
});

function given(at: string | null): string {
  if (!at) return "";
  const [year, month] = at.slice(0, 7).split("-").map(Number);
  return ` in ${WHEN.format(new Date(year, (month || 1) - 1, 1))}`;
}

/**
 * Old scores, one card at a time (Sprint 121, DEC-178, mockup 03): "Still a 9?",
 * keep it or give the one it has now, with why. Every answer is a row of the score's
 * history, so a score looked at rests a year before it comes back. It arrives nowhere
 * uninvited: a chore, opened by choice.
 */
export function RevisitDeckPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const queue = useQuery({
    queryKey: ["chores", "revisit"],
    queryFn: ({ signal }) => getRevisit(signal),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const cards = useMemo(() => queue.data?.cards ?? [], [queue.data]);

  return (
    <Deck<RevisitCard, Draft>
      label="Revisit"
      progressLabel="Progress through old scores"
      closeLabel="Back to Insights"
      onClose={() => navigate("/insights")}
      source={{
        cards,
        total: queue.data?.total ?? 0,
        isPending: queue.isPending,
        isError: queue.isError,
        hasNextPage: false,
        isFetchingNextPage: false,
        fetchNextPage: () => undefined,
        refetch: () => void queue.refetch(),
      }}
      loadingLabel="Gathering old scores…"
      errorTitle="Old scores could not be loaded"
      keyOf={(card) => card.entry.id}
      entryOf={(card) => card.entry}
      initialDraft={(card) => ({
        score: card.entry.score ?? 5,
        reason: "time",
        note: "",
      })}
      stamp={(card, draft) =>
        draft.score === card.entry.score ? "Still" : `${draft.score}`
      }
      filedNoun="looked at"
      // Every answer is history; taking one back would be another row, not an undo.
      canUndo={() => false}
      file={async (card, draft) => {
        await patchEntry(card.entry.id, {
          score: draft.score,
          score_reason: draft.reason,
          ...(draft.note.trim() ? { score_note: draft.note.trim() } : {}),
        });
        void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
        void queryClient.invalidateQueries({
          queryKey: queryKeys.scoreHistory(card.entry.id),
        });
      }}
      unfile={async () => undefined}
      onKey={(event, _card, { setDraft }) => {
        if (/^[0-9]$/.test(event.key)) {
          setDraft({ score: event.key === "0" ? 10 : Number(event.key) });
          return true;
        }
        return false;
      }}
      renderControls={(card, controls) => (
        <Controls card={card} controls={controls} />
      )}
      renderEnd={({ filed, passedNow, waitingPassed, roundAgain, close }) => {
        const changed = filed.filter(
          ({ card, draft }) => draft.score !== card.entry.score,
        ).length;
        return (
          <DeckEnd
            entries={filed.map(({ card }) => card.entry)}
            title={
              waitingPassed ? "That’s the deck" : "Every old score looked at"
            }
            summary={`${filed.length - changed} kept · ${changed} changed${
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
              Back to Insights
            </Button>
          </DeckEnd>
        );
      }}
    />
  );
}

function Controls({
  card,
  controls: { draft, setDraft, commit },
}: {
  card: RevisitCard;
  controls: DeckControls<Draft>;
}) {
  const was = card.entry.score ?? 5;
  const changed = draft.score !== was;
  return (
    <section
      aria-label={`Look again at ${card.entry.item.title}`}
      className="flex shrink-0 flex-col gap-2.5 md:justify-center md:gap-5"
    >
      <div className="text-center md:text-left">
        <h2
          className={cn(
            "line-clamp-3 font-display font-medium leading-tight tracking-tight",
            titleSize(card.entry.item.title),
          )}
          data-testid="deck-title"
        >
          {card.entry.item.title}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          You gave it {was}
          {given(card.scored_at)}.
        </p>
        {card.entry.notes && (
          <p className="mt-1 line-clamp-2 font-display text-base italic md:text-lg">
            “{card.entry.notes}”
          </p>
        )}
      </div>
      <h3 className="text-center font-display text-2xl font-medium md:text-left md:text-3xl">
        Still {scoreArticle(was)}?
      </h3>
      <fieldset>
        <legend className="sr-only">Score</legend>
        <div className="flex gap-1">
          {Array.from({ length: 10 }, (_, index) => index + 1).map((value) => (
            <button
              key={value}
              type="button"
              aria-label={`Score ${value}`}
              aria-pressed={draft.score === value}
              onClick={() => setDraft({ score: value })}
              className={cn(
                "h-9 min-w-0 flex-1 rounded-md text-sm font-medium tabular-nums transition-colors focus-ring md:h-11",
                draft.score === value
                  ? scoreChipClass(value)
                  : "bg-surface text-muted-foreground hover:bg-accent hover:text-foreground",
                value === was &&
                  changed &&
                  "outline-dashed outline-1 outline-offset-2 outline-muted-foreground",
              )}
            >
              {value}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center justify-center gap-2 md:justify-start">
        {(
          [
            ["reread", "Went back to it"],
            ["time", "Time"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={draft.reason === value}
            onClick={() => setDraft({ reason: value })}
            className={cn(
              "h-9 rounded-full border px-4 text-sm transition-colors focus-ring",
              draft.reason === value
                ? "border-primary-text text-primary-text"
                : "border-dashed border-border text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <Input
        aria-label="Why, in a line (optional)"
        value={draft.note}
        maxLength={280}
        placeholder={changed ? "What changed" : "What still holds"}
        onChange={(event) => setDraft({ note: event.target.value })}
      />
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
          onClick={() => commit("file")}
        >
          {changed ? `Change to ${draft.score}` : `Keep ${was}`}
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </section>
  );
}
