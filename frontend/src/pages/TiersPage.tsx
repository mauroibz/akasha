import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getLibraryPage,
  patchEntry,
  rankEntries,
  type LibraryEntry,
} from "@/api/library";
import { queryKeys } from "@/api/keys";
import { CoverImage } from "@/components/CoverImage";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/ui/skeleton";
import { DomainStrip } from "@/components/DomainStrip";
import { domainsFrom } from "@/features/library/labels";
import { defaultLibraryFilters } from "@/features/library/library";
import { useItemTypes } from "@/features/library/useItemTypes";
import { TypesetCover } from "@/features/shelves/OpeningCover";
import {
  boardFrom,
  moveTo,
  proposals,
  rowOf,
  rowsToRank,
  SCORES,
  type Board,
} from "@/features/tiers/board";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/** Every scored entry of one library, all pages of it. */
async function everyScored(type: string, signal?: AbortSignal) {
  const filters = {
    ...defaultLibraryFilters,
    types: [type],
    sort: "score" as const,
    order: "desc" as const,
  };
  const items: LibraryEntry[] = [];
  let cursor: string | undefined;
  do {
    const page = await getLibraryPage(filters, cursor, signal, 200);
    items.push(...page.items.filter((entry) => entry.score !== null));
    cursor = page.next_cursor ?? undefined;
  } while (cursor);
  return items;
}

/**
 * The tier board (Sprint 117, DEC-176): a library's scored entries in rows, ten to
 * one, in their rank order. Tap a cover to pick it up and tap where it goes (or use
 * the arrow keys). Inside a row that is a rank, saved at once; into another row it
 * is a proposal, listed and written only on *Apply*, as `time` in the score history.
 */
export function TiersPage() {
  const itemTypes = useItemTypes();
  const domains = domainsFrom(itemTypes.data);
  const navigate = useNavigate();
  const type = useParams().type ?? domains[0]?.id ?? "";
  const queryClient = useQueryClient();
  const scored = useQuery({
    queryKey: ["tiers", type],
    queryFn: ({ signal }) => everyScored(type, signal),
    enabled: Boolean(type),
    refetchOnWindowFocus: false,
  });
  const entries = useMemo(() => scored.data ?? [], [scored.data]);
  const byId = useMemo(
    () => new Map(entries.map((entry) => [entry.id, entry])),
    [entries],
  );
  const [board, setBoard] = useState<Board | null>(null);
  const saved = useRef<Board | null>(null);
  const [picked, setPicked] = useState<{ id: number; before: Board } | null>(
    null,
  );
  const focusAfter = useRef<number | null>(null);

  useEffect(() => {
    if (!scored.data) return;
    const fresh = boardFrom(scored.data);
    saved.current = fresh;
    setBoard(fresh);
  }, [scored.data]);

  useEffect(() => {
    if (focusAfter.current === null) return;
    document
      .querySelector<HTMLElement>(`[data-tier-entry="${focusAfter.current}"]`)
      ?.focus();
    focusAfter.current = null;
  });

  const saveRanks = useMutation({
    mutationFn: async (rows: number[][]) => {
      for (const row of rows) await rankEntries(row);
    },
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all }),
  });
  const apply = useMutation({
    mutationFn: async (next: Board) => {
      for (const change of proposals(next, entries))
        await patchEntry(change.id, { score: change.to, score_reason: "time" });
      const rows = new Set(
        proposals(next, entries).flatMap((change) => [change.to]),
      );
      for (const score of rows)
        if (next[score].length > 0) await rankEntries(next[score]);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tiers", type] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    },
  });

  if (scored.isPending || !board)
    return (
      <main className="mx-auto w-full max-w-6xl px-5 py-8">
        <Loading label="Laying out the tiers…" />
      </main>
    );

  /** A drop: save what can be saved now, and keep the rest as proposals. */
  const drop = (next: Board, id: number) => {
    setBoard(next);
    setPicked(null);
    focusAfter.current = id;
    const rows = rowsToRank(next, saved.current ?? next, entries);
    if (rows.length) {
      saveRanks.mutate(rows);
      const settled: Board = { ...(saved.current ?? next) };
      for (const row of rows) {
        const score = rowOf(next, row[0]);
        if (score !== null) settled[score] = row;
      }
      saved.current = settled;
    }
  };

  const pick = (id: number) => {
    if (picked?.id === id) {
      drop(board, id);
      return;
    }
    if (picked) {
      // Tapping another cover places the one in hand just before it.
      const score = rowOf(board, id)!;
      drop(
        moveTo(board, picked.id, score, board[score].indexOf(id)),
        picked.id,
      );
      return;
    }
    setPicked({ id, before: board });
  };

  const onKey = (event: React.KeyboardEvent, id: number) => {
    if (!picked || picked.id !== id) return;
    const score = rowOf(board, id)!;
    const index = board[score].indexOf(id);
    const steps: Record<string, [number, number]> = {
      ArrowLeft: [score, index - 1],
      ArrowRight: [score, index + 1],
      ArrowUp: [Math.min(10, score + 1), index],
      ArrowDown: [Math.max(1, score - 1), index],
    };
    if (event.key === "Escape") {
      event.preventDefault();
      setBoard(picked.before);
      setPicked(null);
      focusAfter.current = id;
      return;
    }
    const step = steps[event.key];
    if (!step) return;
    event.preventDefault();
    setBoard(moveTo(board, id, step[0], step[1]));
    focusAfter.current = id;
  };

  const changes = proposals(board, entries);
  const pickedEntry = picked ? byId.get(picked.id) : undefined;

  return (
    <main className="mx-auto w-full max-w-6xl px-5 pb-40 pt-8">
      <PageHeader
        back
        title="Tiers"
        lede={
          pickedEntry
            ? `Holding ${pickedEntry.item.title}. Tap where it goes, or tap it again to put it down.`
            : "Tap a cover to pick it up, then tap where it goes. Within a row it is an order; into another row, a proposal you apply."
        }
      />
      {domains.length > 1 && (
        <DomainStrip
          domains={domains}
          value={type}
          onChange={(id) => {
            setBoard(null);
            setPicked(null);
            navigate(`/tiers/${id}`);
          }}
          className="mt-6"
        />
      )}
      <div className="mt-6 space-y-2">
        {SCORES.map((score) => {
          const row = board[score];
          return (
            <div
              key={score}
              role="group"
              aria-label={String(score)}
              className={cn(
                "flex min-h-[4.5rem] items-stretch gap-3 rounded-xl border border-border bg-surface p-2",
                row.length === 0 && !picked && "min-h-0 border-dashed py-1",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  scoreChipShape,
                  scoreChipClass(score),
                  "flex w-10 shrink-0 items-center justify-center self-center text-lg",
                )}
              >
                {score}
              </span>
              <ol className="flex min-w-0 flex-1 gap-2 overflow-x-auto pb-1">
                {row.map((id) => {
                  const entry = byId.get(id);
                  if (!entry) return null;
                  const moved = entry.score !== score;
                  const holding = picked?.id === id;
                  return (
                    <li key={id} className="shrink-0">
                      <button
                        type="button"
                        data-tier-entry={id}
                        aria-pressed={holding}
                        aria-label={`${entry.item.title}${moved ? `, from ${entry.score}` : ""}${holding ? ", picked up" : ""}`}
                        onClick={() => pick(id)}
                        onKeyDown={(event) => onKey(event, id)}
                        className={cn(
                          "relative block w-14 overflow-hidden rounded-md ring-2 transition focus-ring sm:w-16",
                          holding
                            ? "-translate-y-1 ring-primary"
                            : moved
                              ? "ring-dashed ring-primary/60"
                              : "ring-transparent hover:ring-border",
                        )}
                      >
                        <span className="block aspect-[2/3]">
                          {entry.item.cover_url ? (
                            <CoverImage
                              src={entry.item.cover_url}
                              alt=""
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <TypesetCover
                              title={entry.item.title}
                              seed={entry.id}
                            />
                          )}
                        </span>
                        {moved && (
                          <span className="absolute right-0.5 top-0.5 rounded bg-background/85 px-1 text-[10px] font-semibold tabular-nums">
                            {entry.score}→{score}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
                <li className="shrink-0">
                  <button
                    type="button"
                    disabled={!picked}
                    aria-label={`Place it here, as ${score}`}
                    onClick={() =>
                      picked &&
                      drop(
                        moveTo(board, picked.id, score, row.length),
                        picked.id,
                      )
                    }
                    className={cn(
                      "flex h-full min-h-11 w-14 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground transition focus-ring sm:w-16",
                      picked
                        ? "border-primary/60 hover:bg-primary/10"
                        : "border-transparent",
                    )}
                  >
                    {picked ? "Here" : ""}
                  </button>
                </li>
              </ol>
            </div>
          );
        })}
      </div>

      {changes.length > 0 && (
        <section
          aria-label="Changes to apply"
          className="fixed inset-x-0 bottom-16 z-40 border-t border-border bg-background/95 px-5 pb-3 pt-3 backdrop-blur sm:bottom-0 sm:pb-[max(1rem,env(safe-area-inset-bottom))]"
        >
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
            <ul className="flex min-w-0 flex-1 flex-wrap gap-x-4 gap-y-1 text-sm">
              {changes.map((change) => (
                <li key={change.id}>
                  {byId.get(change.id)?.item.title} {change.from} → {change.to}
                </li>
              ))}
            </ul>
            <Button
              variant="ghost"
              className="rounded-full px-4"
              onClick={() => {
                // Each proposal goes back to its own score; orders already saved stay.
                const original = boardFrom(entries);
                let next = board;
                for (const change of changes)
                  next = moveTo(
                    next,
                    change.id,
                    change.from,
                    Math.max(0, original[change.from].indexOf(change.id)),
                  );
                saved.current = next;
                setBoard(next);
                setPicked(null);
              }}
            >
              Discard
            </Button>
            <Button
              className="rounded-full px-5"
              disabled={apply.isPending}
              onClick={() => apply.mutate(board)}
            >
              Apply {changes.length}{" "}
              {changes.length === 1 ? "change" : "changes"}
            </Button>
          </div>
        </section>
      )}
    </main>
  );
}
