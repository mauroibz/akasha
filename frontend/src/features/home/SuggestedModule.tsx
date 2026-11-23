import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import type { ModuleSize } from "@/api/home";
import { queryKeys } from "@/api/keys";
import type { ItemType } from "@/api/library";
import {
  answerSuggestion,
  type Suggestion,
  type SuggestionAnswer,
} from "@/api/suggestions";
import { CoverImage } from "@/components/CoverImage";
import {
  MoreLikeThisSheet,
  type Seed,
} from "@/features/suggest/MoreLikeThisSheet";
import { attributionsFor } from "@/features/suggest/recommendation";

import { HomeModule } from "./HomeModule";

/** How many suggestions show, by size. */
const SHOWN: Record<ModuleSize, number> = { S: 2, M: 4, L: 8 };

const iconButton =
  "inline-flex h-9 w-9 items-center justify-center rounded-full border border-border transition-colors hover:bg-accent focus-ring disabled:opacity-50 [&_svg]:h-4 [&_svg]:w-4";

/**
 * Home's *More like this* (Sprint 134): the newest suggestions found in a provider
 * and not yet answered, across libraries, from storage only. Each can be wanted or
 * turned down where it stands; opening one shows its whole round in the sheet.
 */
export function SuggestedModule({
  suggestions,
  types,
  size,
}: {
  suggestions: Suggestion[];
  types: ItemType[] | undefined;
  size: ModuleSize;
}) {
  const queryClient = useQueryClient();
  const [seed, setSeed] = useState<Seed | null>(null);
  const answer = useMutation({
    mutationFn: ({
      suggestion,
      value,
    }: {
      suggestion: Suggestion;
      value: SuggestionAnswer;
    }) => answerSuggestion(suggestion.id, value),
    onSuccess: (_saved, { value }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.home });
      if (value === "want")
        void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Your answer was not saved",
      ),
  });
  const shown = suggestions.slice(0, SHOWN[size]);
  const sources = new Set(shown.map((row) => row.source));
  const lines = attributionsFor(sources, types);
  const seeds = new Set(
    shown.flatMap((row) => (row.seed ? [row.seed.title] : [])),
  );

  return (
    <HomeModule
      title="More like this"
      aside={
        seeds.size
          ? `From ${seeds.size} ${seeds.size === 1 ? "seed" : "seeds"}`
          : undefined
      }
    >
      <ul className="grid grid-cols-2 gap-3 min-[480px]:grid-cols-4">
        {shown.map((suggestion) => {
          const name = suggestion.year
            ? `${suggestion.title} (${suggestion.year})`
            : suggestion.title;
          const busy =
            answer.isPending &&
            answer.variables?.suggestion.id === suggestion.id;
          return (
            <li key={suggestion.id} className="flex min-w-0 flex-col gap-1.5">
              <button
                type="button"
                className="rounded focus-ring"
                aria-label={
                  suggestion.seed
                    ? `${name}, more like ${suggestion.seed.title}`
                    : name
                }
                disabled={!suggestion.seed}
                onClick={() =>
                  suggestion.seed &&
                  setSeed({
                    entryId: suggestion.seed.entry_id,
                    title: suggestion.seed.title,
                    type: suggestion.item_type,
                  })
                }
              >
                <CoverImage
                  src={suggestion.cover_url}
                  alt=""
                  className="aspect-[2/3] w-full rounded object-cover"
                />
              </button>
              <p className="line-clamp-2 text-xs font-medium leading-snug">
                {suggestion.title}
              </p>
              {suggestion.seed ? (
                <p className="truncate text-[11px] text-muted-foreground">
                  Like {suggestion.seed.title}
                </p>
              ) : null}
              <div className="flex gap-1.5">
                <button
                  type="button"
                  className={iconButton}
                  disabled={busy}
                  aria-label={`Want ${name}`}
                  title="Want"
                  onClick={() => answer.mutate({ suggestion, value: "want" })}
                >
                  <Plus aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className={iconButton}
                  disabled={busy}
                  aria-label={`Not for me: ${name}`}
                  title="Not for me"
                  onClick={() =>
                    answer.mutate({ suggestion, value: "not_for_me" })
                  }
                >
                  <X aria-hidden="true" />
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      {lines.map((line) => (
        <p
          key={line}
          className="mt-3 text-[11px] leading-snug text-muted-foreground"
        >
          {line}
        </p>
      ))}
      <MoreLikeThisSheet
        seed={seed}
        open={seed !== null}
        onOpenChange={(open) => {
          if (!open) setSeed(null);
        }}
        types={types}
      />
    </HomeModule>
  );
}
