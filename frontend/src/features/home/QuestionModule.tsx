import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import type { HomeQuestion } from "@/api/home";
import { queryKeys } from "@/api/keys";
import type { ItemType } from "@/api/library";
import { Cover } from "@/components/Cover";
import { OneQuestion } from "@/features/questions/OneQuestion";
import { scoreArticle } from "@/features/rescore/rescore";

import { HomeModule } from "./HomeModule";
import { useHomeWrite } from "./useHomeWrite";

/**
 * One question from Play (Sprint 131), answered where it stands: an old score to
 * look at again ("Still a 9" keeps it, as the revisit deck does, and rests it a
 * year), else one gap in an entry, asked as the detail page asks it. Hidden when
 * there is nothing to ask.
 */
export function QuestionModule({
  question,
  types,
  className,
}: {
  question: HomeQuestion;
  types: ItemType[] | undefined;
  className?: string;
}) {
  const write = useHomeWrite();
  const queryClient = useQueryClient();
  const { entry } = question;
  const cover = (
    <Link
      to={`/books/${entry.id}`}
      className="w-12 shrink-0 rounded focus-ring"
      aria-label={`Open ${entry.item.title}`}
    >
      <Cover src={entry.item.cover_url} size="s" />
    </Link>
  );
  return (
    <HomeModule
      title="One question"
      className={className}
      aside={
        <Link
          to="/journal"
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          Play →
        </Link>
      }
    >
      {question.kind === "revisit" && entry.score !== null ? (
        <div className="flex gap-3">
          {cover}
          <div className="min-w-0 flex-1 space-y-2">
            <h3 className="font-display text-lg leading-snug">
              Is <i>{entry.item.title}</i> still {scoreArticle(entry.score)}?
            </h3>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={write.isPending}
                onClick={() =>
                  write.mutate({
                    entry,
                    changes: { score: entry.score, score_reason: "time" },
                  })
                }
                className="inline-flex min-h-9 items-center rounded-full border border-border px-3 text-sm font-medium transition-colors hover:bg-accent focus-ring disabled:opacity-50"
              >
                Still {scoreArticle(entry.score)}
              </button>
              <Link
                to="/deck/revisit"
                className="inline-flex min-h-9 items-center rounded-full border border-border px-3 text-sm font-medium transition-colors hover:bg-accent focus-ring"
              >
                Change
              </Link>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            {cover}
            <p className="min-w-0 truncate font-medium">{entry.item.title}</p>
          </div>
          <OneQuestion
            entry={entry}
            types={types}
            onDone={() =>
              void queryClient.invalidateQueries({ queryKey: queryKeys.home })
            }
          />
        </div>
      )}
    </HomeModule>
  );
}
