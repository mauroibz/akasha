import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  getGaps,
  getLibraryPage,
  getRevisit,
  type ItemType,
  type LibraryEntry,
} from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { plannedFilters } from "@/features/chores/chores";
import { countLabel } from "@/features/library/labels";
import { defaultLibraryFilters } from "@/features/library/library";
import { useScoreDistribution } from "@/features/library/useScoreDistribution";
import { scoreArticle } from "@/features/rescore/rescore";
import { cn } from "@/lib/utils";

import { bestScore, type Game } from "./play";

function monthYear(iso: string): string {
  return new Date(iso).toLocaleDateString("en", {
    month: "long",
    year: "numeric",
  });
}

/**
 * Play with your library (Sprint 125, DEC-179, mockup 2A): the decks, asked as
 * questions about your own books, at the top of Insights. A game appears only when it
 * has something to ask, and the section only when one does. `lead` puts another game
 * first (Sprint 126's mixed round).
 */
export function PlaySection({
  type,
  types,
  lead,
}: {
  type: string;
  types: ItemType[] | undefined;
  lead?: Game | null;
}) {
  const distribution = useScoreDistribution({ type });
  const score = bestScore(distribution.data?.counts ?? []);
  const scored = useQuery({
    queryKey: ["play", "best", type, score],
    queryFn: ({ signal }) =>
      getLibraryPage(
        { ...defaultLibraryFilters, types: [type], score: score! },
        undefined,
        signal,
        3,
      ),
    enabled: Boolean(type) && score !== null,
  });
  const revisit = useQuery({
    queryKey: ["play", "revisit"],
    queryFn: ({ signal }) => getRevisit(signal),
  });
  const planned = plannedFilters(types);
  const pile = useQuery({
    queryKey: ["play", "pile", planned.statuses],
    queryFn: ({ signal }) => getLibraryPage(planned, undefined, signal, 3),
    enabled: planned.statuses.length > 0,
  });
  const gaps = useQuery({
    queryKey: ["play", "gaps"],
    queryFn: ({ signal }) => getGaps(signal),
  });

  const games: Game[] = lead ? [lead] : [];
  if (score !== null && scored.data && scored.data.total >= 2)
    games.push({
      key: "best",
      to: `/rank/${type}/${score}`,
      question: `Which ${score} is your best ${score}?`,
      label: `Which ${score} is your best ${score}?`,
      meta: `${countLabel(scored.data.total, type, types)} · pick one of two`,
      covers: scored.data.items,
    });
  const old = revisit.data?.cards ?? [];
  if (old.length > 0 && old[0].entry.score !== null) {
    const first = old[0].entry;
    games.push({
      key: "revisit",
      to: "/deck/revisit",
      question: (
        <>
          Is <i>{first.item.title}</i> still {scoreArticle(first.score!)}?
        </>
      ),
      label: `Is ${first.item.title} still ${scoreArticle(first.score!)}?`,
      meta: `${revisit.data!.total} old ${revisit.data!.total === 1 ? "score" : "scores"} to look at again`,
      covers: old.slice(0, 3).map((card) => card.entry),
    });
  }
  if (pile.data && pile.data.total > 0)
    games.push({
      key: "pile",
      to: "/deck/planned",
      question: "The pile: still want these?",
      label: "The pile: still want these?",
      meta: `${pile.data.total} waiting, the oldest since ${monthYear(pile.data.items[0].date_added)}`,
      covers: pile.data.items,
    });
  if (gaps.data && gaps.data.total > 0)
    games.push({
      key: "gaps",
      to: "/play/gaps",
      question: "Fill in the gaps",
      label: "Fill in the gaps",
      meta: `${gaps.data.total} finished without a date or a format`,
      covers: gaps.data.entries.slice(0, 3),
    });

  if (games.length === 0) return null;
  return (
    <section id="play" aria-labelledby="play-heading" className="mt-8">
      <h2
        id="play-heading"
        className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground"
      >
        Play with your library
      </h2>
      <ul className="mt-3 grid gap-3 md:grid-cols-2">
        {games.map((game, index) => (
          <li key={game.key}>
            <Link
              to={game.to}
              aria-label={`${game.label} ${game.meta}`}
              className={cn(
                "flex min-h-24 items-center gap-4 rounded-2xl border p-4 transition-colors focus-ring",
                index === 0
                  ? "border-transparent bg-primary/15 hover:bg-primary/20"
                  : "border-border bg-surface hover:bg-accent",
              )}
            >
              <span className="min-w-0 flex-1">
                <span className="block font-display text-xl leading-tight">
                  {game.question}
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">
                  {game.meta}
                </span>
              </span>
              <Fan covers={game.covers} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Up to three covers, fanned. */
function Fan({ covers }: { covers: LibraryEntry[] }) {
  const shown = covers.slice(0, 3);
  return (
    <span aria-hidden="true" className="flex shrink-0 pr-1">
      {shown.map((entry, index) => (
        <CoverImage
          key={entry.id}
          src={entry.item.cover_url ?? null}
          alt=""
          className={cn(
            "aspect-[2/3] w-10 rounded-[2px_5px_5px_2px] object-cover shadow-md",
            index > 0 && "-ml-4",
            shown.length > 1 && index === 0 && "-rotate-6",
            shown.length > 1 && index === shown.length - 1 && "rotate-6",
          )}
        />
      ))}
    </span>
  );
}
