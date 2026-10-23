import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getLibraryPage, rankEntries, type LibraryEntry } from "@/api/library";
import { queryKeys } from "@/api/keys";
import { CoverImage } from "@/components/CoverImage";
import { BackToLibrary } from "@/components/BackToLibrary";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/ui/skeleton";
import { defaultLibraryFilters } from "@/features/library/library";
import {
  answer,
  start,
  type Choice,
  type Ranking,
} from "@/features/rank/insertion";
import { TypesetCover } from "@/features/shelves/OpeningCover";

/**
 * A rank inside a score, chosen two at a time (Sprint 116, DEC-176). The entries that
 * share a score in one library are put in order: each one not yet placed is asked
 * about against the middle of the order so far, and the order is saved after each
 * placement, so leaving halfway keeps what was decided. No score ever changes.
 */
export function RankDeckPage() {
  const { type = "", score: scoreParam = "" } = useParams();
  const score = Number(scoreParam);
  const queryClient = useQueryClient();
  const filters = useMemo(
    () => ({
      ...defaultLibraryFilters,
      types: [type],
      score,
      sort: "score" as const,
      order: "desc" as const,
    }),
    [type, score],
  );
  const group = useQuery({
    queryKey: ["rank", type, score],
    queryFn: ({ signal }) => getLibraryPage(filters, undefined, signal, 200),
    enabled: Boolean(type) && score >= 1 && score <= 10,
    refetchOnWindowFocus: false,
  });
  const entries = useMemo(() => {
    const map = new Map<number, LibraryEntry>();
    for (const entry of group.data?.items ?? []) map.set(entry.id, entry);
    return map;
  }, [group.data]);
  const [state, setState] = useState<Ranking | null>(null);
  const saved = useRef(0);

  useEffect(() => {
    if (!group.data || state) return;
    const items = group.data.items;
    const ranked = items
      .filter((entry) => entry.score_rank != null)
      .sort((a, b) => (a.score_rank ?? 0) - (b.score_rank ?? 0))
      .map((entry) => entry.id);
    saved.current = ranked.length;
    setState(
      start(
        ranked,
        items
          .filter((entry) => entry.score_rank == null)
          .map((entry) => entry.id),
      ),
    );
  }, [group.data, state]);

  const save = useMutation({
    mutationFn: (order: number[]) => rankEntries(order),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all }),
  });

  // Each placement is saved as it lands, so leaving halfway keeps it.
  useEffect(() => {
    if (state && state.ranked.length > saved.current) {
      saved.current = state.ranked.length;
      save.mutate(state.ranked);
    }
  }, [state, save]);

  const choose = (choice: Choice) =>
    setState((current) => (current ? answer(current, choice) : current));

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const keys: Record<string, Choice> = {
        ArrowLeft: "candidate",
        ArrowRight: "against",
        "=": "same",
        s: "skip",
      };
      const choice = keys[event.key];
      if (!choice) return;
      event.preventDefault();
      choose(choice);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const question = state?.question;
  const left = question ? entries.get(question.candidate) : undefined;
  const right = question ? entries.get(question.against) : undefined;
  const toPlace = state ? state.waiting.length : 0;

  return (
    <main className="mx-auto min-h-screen w-full max-w-4xl px-5 pb-24 pt-6 sm:py-8">
      {/* A compact header: on a phone the two covers and the answers have to sit
          above the bottom navigation without scrolling. */}
      <header className="border-b border-border pb-4">
        <BackToLibrary className="mb-3" />
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">
          Your {score}s
        </p>
        <h1 className="mt-1 font-display text-3xl font-medium tracking-tight sm:text-5xl">
          {question ? "Which did you like more?" : `Your ${score}s, in order`}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {question
            ? `${toPlace} to place. No score changes.`
            : "Saved. The library's score sort follows this order."}
        </p>
      </header>
      {group.isPending || !state ? (
        <Loading label="Gathering the scores…" className="mt-10" />
      ) : question && left && right ? (
        <section aria-label="Two to choose between" className="mt-5 sm:mt-8">
          <div className="grid grid-cols-2 gap-4 sm:gap-8">
            {[left, right].map((entry, index) => (
              <button
                key={entry.id}
                type="button"
                aria-label={entry.item.title}
                onClick={() => choose(index === 0 ? "candidate" : "against")}
                className="group flex flex-col items-center gap-3 rounded-2xl p-2 text-center transition-colors hover:bg-accent focus-ring"
              >
                <span className="block aspect-[2/3] w-full max-w-[8rem] overflow-hidden sm:max-w-[16rem] rounded-xl shadow-xl ring-1 ring-border transition-transform group-hover:-translate-y-1 motion-reduce:transition-none">
                  {entry.item.cover_url ? (
                    <CoverImage
                      src={entry.item.cover_url}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <TypesetCover title={entry.item.title} seed={entry.id} />
                  )}
                </span>
                <span className="line-clamp-2 font-display text-lg font-medium leading-tight sm:text-2xl">
                  {entry.item.title}
                </span>
                <span className="text-sm text-muted-foreground">
                  {entry.item.creator ?? "Unknown"}
                </span>
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap justify-center gap-3 sm:mt-6">
            <Button
              variant="secondary"
              className="rounded-full px-5"
              onClick={() => choose("same")}
            >
              About the same
            </Button>
            <Button
              variant="ghost"
              className="rounded-full px-5"
              onClick={() => choose("skip")}
            >
              Skip this one
            </Button>
          </div>
          <p className="mt-4 hidden text-center text-xs text-muted-foreground md:block">
            <kbd>←</kbd> the left · <kbd>→</kbd> the right · <kbd>=</kbd> about
            the same · <kbd>s</kbd> skip
          </p>
        </section>
      ) : (
        <section className="mt-8">
          <ol
            aria-label={`Your ${score}s, in order`}
            className="divide-y divide-border"
          >
            {state.ranked.map((id, index) => {
              const entry = entries.get(id);
              if (!entry) return null;
              return (
                <li key={id} className="flex items-center gap-4 py-3">
                  <span className="w-6 text-right font-display text-xl tabular-nums text-muted-foreground">
                    {index + 1}
                  </span>
                  <span className="block w-10 shrink-0 overflow-hidden rounded">
                    {entry.item.cover_url ? (
                      <CoverImage
                        src={entry.item.cover_url}
                        alt=""
                        className="aspect-[2/3] w-10 object-cover"
                      />
                    ) : (
                      <span className="block aspect-[2/3] w-10">
                        <TypesetCover
                          title={entry.item.title}
                          seed={entry.id}
                        />
                      </span>
                    )}
                  </span>
                  <Link
                    to={`/books/${entry.id}`}
                    className="min-w-0 truncate font-medium underline-offset-4 hover:underline focus-ring"
                  >
                    {entry.item.title}
                  </Link>
                </li>
              );
            })}
          </ol>
          {state.skipped.length > 0 && (
            <p className="mt-4 text-sm text-muted-foreground">
              {state.skipped.length} skipped; they wait for next time.
            </p>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <Button asChild className="rounded-full px-5">
              <Link to="/rank">Order another score</Link>
            </Button>
            <Button asChild variant="secondary" className="rounded-full px-5">
              <Link to="/insights">Back to Insights</Link>
            </Button>
          </div>
        </section>
      )}
    </main>
  );
}
