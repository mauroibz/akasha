import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import type { ItemType } from "@/api/library";
import {
  FINISHED_ROUNDS,
  answerSuggestion,
  enrichSuggestion,
  getSuggestionRound,
  moreLikeThis,
  type Suggestion,
  type SuggestionAnswer,
  type SuggestionRound,
} from "@/api/suggestions";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useJobEvent } from "@/features/activity/jobEvents";
import { cn } from "@/lib/utils";

import { firstSource, recommendationFor } from "./recommendation";

export interface Seed {
  entryId: number;
  title: string;
  type: string;
}

const answered: Record<SuggestionAnswer, string> = {
  want: "On your list",
  not_for_me: "Not for you",
  seen: "Seen it",
};

/** What a round is doing, in words, while it is not done. */
function progressLine(round: SuggestionRound, label: string): string | null {
  switch (round.status) {
    case "queued":
    case "selecting":
      return `Asking ${label}…`;
    case "enriching":
      return "Finding the first few in your providers…";
    default:
      return null;
  }
}

/**
 * The art a suggestion has: the cover its domain's providers found, served by
 * Akasha, or its title set as type while it has none. Never an image from the
 * source itself (DEC-189).
 */
function Art({ suggestion }: { suggestion: Suggestion }) {
  if (suggestion.cover_url)
    return (
      <CoverImage
        src={suggestion.cover_url}
        alt=""
        className="aspect-[2/3] w-full rounded object-cover"
      />
    );
  return (
    <div
      aria-hidden="true"
      className="flex aspect-[2/3] w-full flex-col justify-end overflow-hidden rounded bg-surface-raised p-1 font-display text-[10px] leading-tight text-foreground"
    >
      <span className="line-clamp-4 hyphens-auto break-words">
        {suggestion.title}
      </span>
      {suggestion.year ? (
        <span className="text-[9px] text-muted-foreground">
          {suggestion.year}
        </span>
      ) : null}
    </div>
  );
}

/**
 * *More like this* (Sprint 134, the mockup's sheet): one round of one source for
 * one entry. Pressing the button asks once (or shows the round from the last day);
 * the round's job reports on the event stream and the sheet re-reads the stored
 * round each time, so picks and their enrichment arrive while it is open. The
 * first few are looked up straight away; opening a pending one looks it up. Each
 * can be wanted (onto the list), turned down, or marked seen; *Refresh* asks again.
 */
export function MoreLikeThisSheet({
  seed,
  open,
  onOpenChange,
  types,
}: {
  seed: Seed | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  types: ItemType[] | undefined;
}) {
  const queryClient = useQueryClient();
  const info = seed ? recommendationFor(seed.type, types) : null;
  const source = info ? firstSource(info) : null;
  const [roundId, setRoundId] = useState<number | null>(null);
  const [looking, setLooking] = useState<ReadonlySet<number>>(new Set());
  const asked = useRef<number | null>(null);

  const start = useMutation({
    mutationFn: ({ entryId, refresh }: { entryId: number; refresh: boolean }) =>
      moreLikeThis(entryId, { refresh }),
    onSuccess: (found) => {
      queryClient.setQueryData(queryKeys.suggestionRound(found.id), found);
      setRoundId(found.id);
      setLooking(new Set());
    },
    onError: (error) =>
      toast.error(
        error instanceof Error
          ? error.message
          : "Suggestions could not be asked for",
      ),
  });

  // Ask once per seed opened, and only a source that can answer: one that is not
  // configured is explained without a request.
  useEffect(() => {
    if (!open || !seed || !source?.configured) return;
    if (asked.current === seed.entryId) return;
    asked.current = seed.entryId;
    setRoundId(null);
    start.mutate({ entryId: seed.entryId, refresh: false });
  }, [open, seed, source?.configured, start]);

  const round = useQuery({
    queryKey: queryKeys.suggestionRound(roundId ?? 0),
    queryFn: ({ signal }) => getSuggestionRound(roundId ?? 0, signal),
    enabled: roundId !== null,
    staleTime: Infinity,
  });
  const data = roundId !== null ? round.data : undefined;

  useJobEvent((event) => {
    if (roundId === null || !data) return;
    const progress = event.progress as Record<string, unknown>;
    const ours =
      (event.kind === "recommend" && progress.round_id === roundId) ||
      (event.kind === "enrich_suggestion" &&
        data.suggestions.some((row) => row.id === progress.suggestion_id));
    if (!ours) return;
    void queryClient.invalidateQueries({
      queryKey: queryKeys.suggestionRound(roundId),
    });
  });

  const replace = (saved: Suggestion) => {
    if (roundId === null) return;
    queryClient.setQueryData<SuggestionRound>(
      queryKeys.suggestionRound(roundId),
      (before) =>
        before && {
          ...before,
          suggestions: before.suggestions.map((row) =>
            row.id === saved.id ? saved : row,
          ),
        },
    );
  };

  const answer = useMutation({
    mutationFn: ({
      suggestion,
      value,
    }: {
      suggestion: Suggestion;
      value: SuggestionAnswer | null;
    }) => answerSuggestion(suggestion.id, value),
    onSuccess: (saved, { value, suggestion }) => {
      replace(saved);
      void queryClient.invalidateQueries({ queryKey: queryKeys.home });
      if (value === "want" || suggestion.answer === "want") {
        void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      }
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Your answer was not saved",
      ),
  });

  const lookUp = useMutation({
    mutationFn: (suggestion: Suggestion) => enrichSuggestion(suggestion.id),
    onMutate: (suggestion) =>
      setLooking((before) => new Set(before).add(suggestion.id)),
    onSuccess: ({ suggestion, job_id }) => {
      replace(suggestion);
      if (job_id === null)
        setLooking((before) => {
          const next = new Set(before);
          next.delete(suggestion.id);
          return next;
        });
    },
    onError: (error, suggestion) => {
      setLooking((before) => {
        const next = new Set(before);
        next.delete(suggestion.id);
        return next;
      });
      toast.error(
        error instanceof Error ? error.message : "It could not be looked up",
      );
    },
  });

  const label = source?.label ?? "the source";
  const attribution = source ? info?.attribution[source.name] : undefined;
  const shown = (data?.suggestions ?? []).filter(
    (row) => row.enrichment !== "unresolved",
  );
  const found = shown.filter((row) => row.enrichment === "enriched").length;
  const finished = data ? FINISHED_ROUNDS.has(data.status) : false;
  const working = start.isPending || (data !== undefined && !finished);

  let body;
  if (!seed || !info || !source) {
    body = null;
  } else if (!source.configured) {
    body = (
      <p className="rounded-lg border border-border bg-surface p-3 text-sm">
        {source.hint ?? `${source.label} is not configured on this server.`}
      </p>
    );
  } else if (!data) {
    body = (
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {start.isError
          ? "Suggestions could not be asked for."
          : `Asking ${label}…`}
      </p>
    );
  } else if (
    data.status === "not_configured" ||
    data.status === "over_budget" ||
    data.status === "failed"
  ) {
    body = (
      <p className="rounded-lg border border-border bg-surface p-3 text-sm">
        {data.error ?? "No suggestions this time."}
      </p>
    );
  } else {
    body = (
      <>
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {progressLine(data, label) ??
            (shown.length
              ? `${shown.length} picked by ${label} in one request · ${found} found so far`
              : `${label} had nothing new to suggest.`)}
          {data.status === "done" && data.error ? ` · ${data.error}` : null}
        </p>
        {shown.length ? (
          <ul className="divide-y divide-border" aria-label="Suggestions">
            {shown.map((suggestion) => (
              <Row
                key={suggestion.id}
                suggestion={suggestion}
                looking={looking.has(suggestion.id)}
                busy={
                  answer.isPending &&
                  answer.variables?.suggestion.id === suggestion.id
                }
                onAnswer={(value) => answer.mutate({ suggestion, value })}
                onLookUp={() => lookUp.mutate(suggestion)}
                onOpenEntry={() => onOpenChange(false)}
              />
            ))}
          </ul>
        ) : null}
      </>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "gap-3",
          // A side sheet from 640px (the mockup's), a bottom sheet on a phone.
          "sm:inset-y-0 sm:left-auto sm:right-0 sm:top-0 sm:h-dvh sm:max-h-none sm:w-[28rem] sm:max-w-[100vw] sm:translate-x-0 sm:translate-y-0 sm:content-start sm:rounded-none sm:border-y-0 sm:border-r-0 sm:border-l sm:data-[state=closed]:zoom-out-100 sm:data-[state=open]:zoom-in-100",
        )}
      >
        <DialogHeader className="pr-8 text-left">
          <DialogTitle className="font-display text-xl font-medium">
            More like {seed?.title ?? "this"}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {info && info.sources.length > 1
              ? `Suggestions from ${info.sources.map((row) => row.label).join(" or ")}.`
              : `Suggestions from ${label}, looked up in your own providers.`}
          </DialogDescription>
        </DialogHeader>
        {info && info.sources.length > 0 ? (
          <div className="flex items-center justify-between gap-3">
            <span
              className="inline-flex rounded-full border border-border p-0.5 text-xs"
              aria-label="Source"
            >
              {info.sources.map((row) => (
                <span
                  key={row.name}
                  className={cn(
                    "rounded-full px-2.5 py-1",
                    row.name === source?.name
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  {row.label}
                </span>
              ))}
            </span>
            {source?.configured && seed ? (
              <Button
                variant="outline"
                size="sm"
                className="rounded-full"
                disabled={working}
                onClick={() =>
                  start.mutate({ entryId: seed.entryId, refresh: true })
                }
              >
                Refresh
              </Button>
            ) : null}
          </div>
        ) : null}
        {body}
        {attribution ? (
          <p className="text-[11px] leading-snug text-muted-foreground">
            {attribution}
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function Row({
  suggestion,
  looking,
  busy,
  onAnswer,
  onLookUp,
  onOpenEntry,
}: {
  suggestion: Suggestion;
  looking: boolean;
  busy: boolean;
  onAnswer: (value: SuggestionAnswer | null) => void;
  onLookUp: () => void;
  onOpenEntry: () => void;
}) {
  const enriched = suggestion.enrichment === "enriched";
  const name = suggestion.year
    ? `${suggestion.title} (${suggestion.year})`
    : suggestion.title;
  return (
    <li className="grid grid-cols-[3rem_minmax(0,1fr)] gap-x-3 gap-y-1.5 py-2.5">
      <div className="row-span-2 w-12">
        <Art suggestion={suggestion} />
      </div>
      <div className="min-w-0">
        <p className="font-display text-base leading-snug">
          {suggestion.title}
          {suggestion.year ? (
            <span className="ml-1.5 text-xs text-muted-foreground">
              {suggestion.year}
            </span>
          ) : null}
        </p>
        {suggestion.reason ? (
          <p className="text-xs text-muted-foreground">
            {suggestion.reason.text}
          </p>
        ) : null}
        <p
          className={cn(
            "text-[11px]",
            enriched ? "text-foreground" : "text-muted-foreground",
          )}
        >
          {enriched
            ? "Found in your providers"
            : looking
              ? "Looking it up…"
              : "Looked up when you open it"}
        </p>
      </div>
      <div className="col-start-2 flex flex-wrap items-center gap-1.5">
        {suggestion.answer ? (
          <>
            {suggestion.answer === "want" && suggestion.entry_id ? (
              <Link
                to={`/books/${suggestion.entry_id}`}
                onClick={onOpenEntry}
                className="text-xs font-medium underline-offset-2 hover:underline focus-ring"
              >
                {answered.want}
              </Link>
            ) : (
              <span className="text-xs font-medium">
                {answered[suggestion.answer]}
              </span>
            )}
            {suggestion.answer !== "want" ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 rounded-full px-2.5"
                disabled={busy}
                aria-label={`Undo your answer on ${name}`}
                onClick={() => onAnswer(null)}
              >
                Undo
              </Button>
            ) : null}
          </>
        ) : (
          <>
            {enriched ? (
              <Button
                size="sm"
                className="h-8 rounded-full px-3"
                disabled={busy}
                aria-label={`Want ${name}`}
                onClick={() => onAnswer("want")}
              >
                Want
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="h-8 rounded-full px-3"
                disabled={looking}
                aria-label={`Look up ${name}`}
                onClick={onLookUp}
              >
                {looking ? "Looking…" : "Look up"}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              className="h-8 rounded-full px-3"
              disabled={busy}
              aria-label={`Not for me: ${name}`}
              onClick={() => onAnswer("not_for_me")}
            >
              Not for me
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 rounded-full px-3"
              disabled={busy}
              aria-label={`Seen ${name}`}
              onClick={() => onAnswer("seen")}
            >
              Seen it
            </Button>
          </>
        )}
      </div>
    </li>
  );
}
