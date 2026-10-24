import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { queryKeys } from "@/api/keys";
import {
  bulkDeleteEntries,
  getGaps,
  getLibraryPage,
  getRevisit,
  patchEntry,
  rankEntries,
  type ItemType,
  type LibraryEntry,
} from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { PageHeader } from "@/components/PageHeader";
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
import { Loading } from "@/components/ui/skeleton";
import { plannedFilters } from "@/features/chores/chores";
import {
  mixRound,
  orderAfter,
  pairFrom,
  type FiveCard,
} from "@/features/five/five";
import { domainsFrom } from "@/features/library/labels";
import { defaultLibraryFilters } from "@/features/library/library";
import { useItemTypes } from "@/features/library/useItemTypes";
import { useScoreDistribution } from "@/features/library/useScoreDistribution";
import { bestScore } from "@/features/play/play";
import { OneQuestion } from "@/features/questions/OneQuestion";
import { scoreArticle } from "@/features/rescore/rescore";
import { scoreChipClass } from "@/lib/score";
import { cn } from "@/lib/utils";

/**
 * Five minutes (Sprint 126, DEC-179, mockup 2C): one mixed round of up to five cards
 * drawn from every game (a pair to put in order, a gap, an old score, something from
 * the pile), each answer written as its own game writes it, ending with what changed.
 * Letting go is asked once more at the end, as the pile's own deck asks.
 */
export function FivePage() {
  const itemTypes = useItemTypes();
  const type = domainsFrom(itemTypes.data)[0]?.id ?? "";
  const distribution = useScoreDistribution({ type });
  const score = distribution.data
    ? bestScore(distribution.data.counts ?? [])
    : undefined;
  const ordered = useQuery({
    queryKey: ["play", "five", "order", type, score],
    queryFn: ({ signal }) =>
      getLibraryPage(
        {
          ...defaultLibraryFilters,
          types: [type],
          score: score!,
          sort: "score",
          order: "desc",
        },
        undefined,
        signal,
        100,
      ),
    enabled: Boolean(type) && typeof score === "number",
  });
  const gaps = useQuery({
    queryKey: ["play", "five", "gaps"],
    queryFn: ({ signal }) => getGaps(signal),
  });
  const revisit = useQuery({
    queryKey: ["play", "five", "revisit"],
    queryFn: ({ signal }) => getRevisit(signal),
  });
  const planned = plannedFilters(itemTypes.data);
  const pile = useQuery({
    queryKey: ["play", "five", "pile", planned.statuses],
    queryFn: ({ signal }) => getLibraryPage(planned, undefined, signal, 2),
    enabled: itemTypes.isSuccess && planned.statuses.length > 0,
  });

  // The round is dealt once, when every source has answered: an answer must never
  // reshuffle the cards still to come.
  const [round, setRound] = useState<FiveCard[] | null>(null);
  const ready =
    itemTypes.isSuccess &&
    distribution.isFetched &&
    (score == null || ordered.isFetched) &&
    gaps.isFetched &&
    revisit.isFetched &&
    (planned.statuses.length === 0 || pile.isFetched);
  useEffect(() => {
    if (!ready || round) return;
    setRound(
      mixRound({
        pair: pairFrom(ordered.data?.items ?? []),
        gaps: (gaps.data?.entries ?? []).slice(0, 2),
        old: (revisit.data?.cards ?? []).slice(0, 2).map((card) => card.entry),
        pile: (pile.data?.items ?? []).slice(0, 2),
      }),
    );
  }, [ready, round, ordered.data, gaps.data, revisit.data, pile.data]);

  const [index, setIndex] = useState(0);
  const [changes, setChanges] = useState<string[]>([]);
  const [letGo, setLetGo] = useState<LibraryEntry[]>([]);
  const next = (change?: string) => {
    if (change) setChanges((rows) => [...rows, change]);
    setIndex((value) => value + 1);
  };
  const card = round?.[index];

  return (
    <main className="mx-auto min-h-screen w-full max-w-xl px-5 pb-24 pt-8">
      <PageHeader
        back={{ to: "/insights", label: "Insights" }}
        eyebrow="Play"
        title="Five minutes"
        count={
          card && round ? (
            <span className="tabular-nums">
              {index + 1} of {round.length}
            </span>
          ) : undefined
        }
      />
      {round && round.length > 0 && (
        <div className="mt-4 flex gap-1" aria-hidden="true">
          {round.map((_, at) => (
            <span
              key={at}
              className={cn(
                "h-1 flex-1 rounded-full",
                at <= index ? "bg-primary" : "bg-muted",
              )}
            />
          ))}
        </div>
      )}
      {!round ? (
        <Loading label="Dealing a round…" className="mt-10" />
      ) : card ? (
        <Card
          key={index}
          card={card}
          ordered={ordered.data?.items ?? []}
          types={itemTypes.data}
          onNext={next}
          onLetGo={(entry) => {
            setLetGo((rows) => [...rows, entry]);
            next();
          }}
        />
      ) : (
        <End changes={changes} letGo={letGo} />
      )}
    </main>
  );
}

function Card({
  card,
  ordered,
  types,
  onNext,
  onLetGo,
}: {
  card: FiveCard;
  ordered: LibraryEntry[];
  types: ItemType[] | undefined;
  onNext: (change?: string) => void;
  onLetGo: (entry: LibraryEntry) => void;
}) {
  const queryClient = useQueryClient();
  const write = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all }),
  });

  if (card.kind === "pair") {
    const [upper, lower] = card.pair;
    const choose = (winner: LibraryEntry, loser: LibraryEntry) =>
      write.mutate(() => rankEntries(orderAfter(ordered, card.pair, winner)), {
        onSuccess: () =>
          onNext(`${winner.item.title} above ${loser.item.title}`),
      });
    return (
      <section className="mt-8" aria-labelledby="five-question">
        <h2 id="five-question" className="font-display text-3xl font-medium">
          Which did you like more?
        </h2>
        <div className="mt-6 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
          <Choice entry={upper} onClick={() => choose(upper, lower)} />
          <span className="font-display text-lg italic text-muted-foreground">
            or
          </span>
          <Choice entry={lower} onClick={() => choose(lower, upper)} />
        </div>
        <Later onClick={() => onNext()} />
        <Failure error={write.error} />
      </section>
    );
  }

  if (card.kind === "gap")
    return (
      <section className="mt-8">
        <Header entry={card.entry} />
        <OneQuestion
          entry={card.entry}
          types={types}
          onDone={(outcome) =>
            onNext(
              outcome === "answered"
                ? `Filled in ${card.entry.item.title}`
                : undefined,
            )
          }
        />
      </section>
    );

  if (card.kind === "old")
    return <OldScore entry={card.entry} onNext={onNext} />;

  return (
    <section className="mt-8" aria-labelledby="five-question">
      <Header entry={card.entry} />
      <h2
        id="five-question"
        className="mt-6 font-display text-3xl font-medium leading-tight"
      >
        Still want {card.entry.item.title}?
      </h2>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button
          variant="outline"
          className="rounded-full px-5"
          onClick={() => onLetGo(card.entry)}
        >
          Let go
        </Button>
        <Button
          className="rounded-full px-5"
          onClick={() => onNext(`Kept ${card.entry.item.title}`)}
        >
          Keep
        </Button>
      </div>
      <Later onClick={() => onNext()} />
    </section>
  );
}

function OldScore({
  entry,
  onNext,
}: {
  entry: LibraryEntry;
  onNext: (change?: string) => void;
}) {
  const queryClient = useQueryClient();
  const was = entry.score!;
  const [score, setScore] = useState(was);
  const save = useMutation({
    mutationFn: () => patchEntry(entry.id, { score, score_reason: "time" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.scoreHistory(entry.id),
      });
      onNext(
        score === was
          ? `${entry.item.title} is still ${scoreArticle(was)}`
          : `${entry.item.title}: ${was} to ${score}`,
      );
    },
  });
  return (
    <section className="mt-8" aria-labelledby="five-question">
      <Header entry={entry} />
      <h2
        id="five-question"
        className="mt-6 font-display text-3xl font-medium leading-tight"
      >
        Is {entry.item.title} still {scoreArticle(was)}?
      </h2>
      <div className="mt-5 flex gap-1">
        {Array.from({ length: 10 }, (_, at) => at + 1).map((value) => (
          <button
            key={value}
            type="button"
            aria-label={`Score ${value}`}
            aria-pressed={score === value}
            onClick={() => setScore(value)}
            className={cn(
              "h-10 min-w-0 flex-1 rounded-md text-sm font-medium tabular-nums transition-colors focus-ring",
              score === value
                ? scoreChipClass(value)
                : "bg-surface text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {value}
          </button>
        ))}
      </div>
      <div className="mt-5 flex flex-wrap gap-3">
        <Button
          className="rounded-full px-5"
          disabled={save.isPending}
          onClick={() => save.mutate()}
        >
          {score === was ? `Keep ${was}` : `Change to ${score}`}
        </Button>
      </div>
      <Later onClick={() => onNext()} />
      <Failure error={save.error} />
    </section>
  );
}

function Header({ entry }: { entry: LibraryEntry }) {
  return (
    <div className="flex items-end gap-4">
      <CoverImage
        src={entry.item.cover_url ?? null}
        alt=""
        className="aspect-[2/3] w-20 shrink-0 rounded-[3px_7px_7px_3px] object-cover shadow-md"
      />
      <p className="min-w-0 font-display text-2xl leading-tight">
        {entry.item.title}
      </p>
    </div>
  );
}

function Choice({
  entry,
  onClick,
}: {
  entry: LibraryEntry;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group min-w-0 rounded-lg text-left focus-ring"
    >
      <CoverImage
        src={entry.item.cover_url ?? null}
        alt=""
        className="aspect-[2/3] w-full rounded-[3px_8px_8px_3px] object-cover shadow-lg transition-transform group-hover:-translate-y-1 motion-reduce:transition-none"
      />
      <span className="mt-2 block truncate text-sm font-medium">
        {entry.item.title}
      </span>
    </button>
  );
}

function Later({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-4 min-h-11 text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
    >
      Later
    </button>
  );
}

function Failure({ error }: { error: Error | null }) {
  return error ? (
    <p role="alert" className="mt-3 text-sm text-destructive">
      {error.message}
    </p>
  ) : null;
}

function End({ changes, letGo }: { changes: string[]; letGo: LibraryEntry[] }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [removed, setRemoved] = useState(false);
  const remove = useMutation({
    mutationFn: () =>
      bulkDeleteEntries({ entry_ids: letGo.map((entry) => entry.id) }),
    onSuccess: () => {
      setConfirming(false);
      setRemoved(true);
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    },
  });
  return (
    <section className="mt-10" aria-labelledby="five-end">
      <h2 id="five-end" className="font-display text-3xl font-medium">
        Five minutes, done
      </h2>
      {changes.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {changes.map((change) => (
            <li key={change} className="font-display text-lg">
              {change}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-muted-foreground">Nothing changed this time.</p>
      )}
      <div className="mt-8 flex flex-wrap gap-3">
        {letGo.length > 0 && !removed && (
          <Button
            variant="destructive"
            className="rounded-full px-5"
            onClick={() => setConfirming(true)}
          >
            Remove the {letGo.length} you let go
          </Button>
        )}
        <Button
          className="rounded-full px-5"
          onClick={() => navigate("/insights")}
        >
          Back to Insights
        </Button>
        <Link
          to="/play/five"
          reloadDocument
          className="inline-flex min-h-11 items-center text-sm font-medium underline-offset-4 hover:underline focus-ring"
        >
          Another round
        </Link>
      </div>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Remove {letGo.length} from your library?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {letGo.map((entry) => entry.item.title).join(", ")}. Their status,
              notes and shelves go with them.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Failure error={remove.error} />
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(
                buttonVariants({ variant: "destructive" }),
                "rounded-full px-5",
              )}
              onClick={(event) => {
                event.preventDefault();
                remove.mutate();
              }}
            >
              Remove {letGo.length}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
