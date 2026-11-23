import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  createEntry,
  NearMatchError,
  searchCandidates,
  type SearchCandidate,
} from "@/api/add";
import { queryKeys } from "@/api/keys";
import { searchLibrary, type LibraryEntry } from "@/api/library";
import { DomainStrip } from "@/components/DomainStrip";
import { Input } from "@/components/ui/input";
import { useShownItemTypes } from "@/features/media/useMedia";

const row =
  "flex min-h-11 w-full items-center gap-3 rounded-lg px-2 text-left text-sm hover:bg-accent focus-ring";

/**
 * *Something else* (Sprint 149, DEC-195): the day was for a thing that is not under
 * way, or not in the library yet. Typing looks in the library, quietly. The web is
 * asked only when *Search the web* is pressed, once per press, because a provider
 * has a quota and a keystroke is not a question (DEC-065). Adding a web result
 * makes the entry with its medium's own default status and hands it back chosen.
 */
export function DaySearch({
  chosen,
  onChoose,
}: {
  /** Entries already chosen for the day, so a result can say so. */
  chosen: number[];
  onChoose: (entry: LibraryEntry) => void;
}) {
  const queryClient = useQueryClient();
  const shown = useShownItemTypes();
  const media = shown.data ?? [];
  const [typed, setTyped] = useState("");
  const [settled, setSettled] = useState("");
  const [medium, setMedium] = useState<string | null>(null);
  const [asked, setAsked] = useState<{ q: string; type: string } | null>(null);
  const type = medium ?? media[0]?.id ?? "";
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(typed.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [typed]);

  const mine = useQuery({
    queryKey: ["day-search", "library", settled],
    queryFn: ({ signal }) => searchLibrary(settled, signal),
    enabled: settled.length >= 2,
    retry: false,
  });
  const web = useQuery({
    queryKey: ["day-search", "web", asked?.q, asked?.type],
    queryFn: ({ signal }) => searchCandidates(asked!.q, asked!.type, signal),
    enabled: asked !== null,
    retry: false,
    staleTime: Infinity,
  });
  const add = useMutation({
    mutationFn: (candidate: SearchCandidate) =>
      createEntry({
        source: candidate.source,
        source_id: candidate.source_id,
        source_refs: candidate.source_refs,
        shelf_ids: [],
      }),
    onSuccess: (result) => {
      onChoose(result.entry);
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.home });
    },
  });

  const found = Array.isArray(mine.data) ? mine.data.slice(0, 6) : [];
  const candidates = Array.isArray(web.data?.items)
    ? web.data.items.slice(0, 5)
    : [];
  return (
    <div className="mt-3 max-w-md">
      <label className="block text-sm font-medium" htmlFor="day-search">
        Find it
      </label>
      <Input
        id="day-search"
        type="search"
        autoFocus
        value={typed}
        onChange={(event) => setTyped(event.target.value)}
        placeholder="A title or a creator"
        className="mt-1 h-11"
      />
      {settled.length >= 2 && (
        <div className="mt-2" aria-live="polite">
          {found.length > 0 ? (
            <ul aria-label="In your library">
              {found.map((entry) => (
                <li key={entry.id}>
                  <button
                    type="button"
                    className={row}
                    aria-pressed={chosen.includes(entry.id)}
                    onClick={() => onChoose(entry)}
                  >
                    <span className="min-w-0 flex-1 truncate font-medium">
                      {entry.item.title}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {chosen.includes(entry.id) ? "Chosen" : "In your library"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : mine.isFetched ? (
            <p className="text-sm text-muted-foreground">
              Nothing in your library by that name.
            </p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
            {media.length > 1 && (
              <DomainStrip
                label="Search the web for"
                domains={media.map((item) => ({
                  id: item.id,
                  label: item.label,
                }))}
                value={type}
                onChange={setMedium}
              />
            )}
            <button
              type="button"
              disabled={!type || web.isFetching}
              onClick={() => setAsked({ q: settled, type })}
              className="min-h-11 text-sm font-medium underline decoration-primary decoration-2 underline-offset-4 focus-ring disabled:opacity-50"
            >
              Search the web
            </button>
          </div>
          {web.isFetching && (
            <p className="text-sm text-muted-foreground">Searching…</p>
          )}
          {web.isError && (
            <p role="alert" className="text-sm text-destructive">
              The web could not be searched just now.
            </p>
          )}
          {asked && web.isSuccess && candidates.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nothing found for “{asked.q}”.
            </p>
          )}
          {candidates.length > 0 && (
            <ul aria-label="On the web" className="mt-1">
              {candidates.map((candidate) => (
                <li key={`${candidate.source}:${candidate.source_id}`}>
                  <button
                    type="button"
                    className={row}
                    disabled={add.isPending}
                    aria-label={`Add ${candidate.title} and choose it`}
                    onClick={() => add.mutate(candidate)}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      <span className="font-medium">{candidate.title}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {[candidate.creators?.[0], candidate.year]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </span>
                    <span className="shrink-0 rounded-full bg-primary px-2.5 py-0.5 text-xs font-semibold text-primary-foreground">
                      Add
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {add.isError && (
            <p role="alert" className="mt-1 text-sm text-destructive">
              {add.error instanceof NearMatchError
                ? "You may already have this one: look for it in your library above."
                : "That could not be added."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
