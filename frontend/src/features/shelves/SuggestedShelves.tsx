import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import {
  acceptShelfSuggestion,
  dismissShelfSuggestion,
  getShelfSuggestions,
} from "@/api/shelves";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import { TypesetCover } from "@/features/shelves/OpeningCover";

const suggestionsKey = ["shelves", "suggestions"] as const;

/**
 * Shelves the library already implies, at the top of the Shelves room (Sprint 119,
 * DEC-176): the same creator three times, a series, one work in two libraries. Read
 * from stored data only; made in one tap, or let go for good. Nothing shows when
 * there is nothing to suggest.
 */
export function SuggestedShelves() {
  const queryClient = useQueryClient();
  const suggestions = useQuery({
    queryKey: suggestionsKey,
    queryFn: ({ signal }) => getShelfSuggestions(signal),
    retry: false,
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: suggestionsKey });
    void queryClient.invalidateQueries({ queryKey: queryKeys.shelves });
  };
  const accept = useMutation({
    mutationFn: acceptShelfSuggestion,
    onSuccess: (shelf) => {
      toast(`Made the shelf ${shelf.name}`);
      refresh();
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const dismiss = useMutation({
    mutationFn: dismissShelfSuggestion,
    onSuccess: refresh,
    onError: (error: Error) => toast.error(error.message),
  });
  const rows = Array.isArray(suggestions.data) ? suggestions.data : [];
  if (rows.length === 0) return null;

  return (
    <section aria-label="Suggested shelves" className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.3em] text-primary-text">
        Suggested
      </h2>
      <ul className="-mx-5 mt-3 flex gap-4 overflow-x-auto px-5 pb-2 md:mx-0 md:px-0">
        {rows.map((row) => (
          <li key={row.key} className="shrink-0">
            <div
              role="group"
              aria-label={row.name}
              className="flex w-64 flex-col gap-3 rounded-xl border border-dashed border-border bg-surface p-4"
            >
              <div className="relative h-24" aria-hidden="true">
                {row.members.slice(0, 4).map((member, index) => (
                  <span
                    key={member.entry_id}
                    className="absolute top-0 block h-24 w-16 overflow-hidden rounded shadow-md ring-1 ring-border"
                    style={{
                      left: `${index * 2.5}rem`,
                      transform: `rotate(${(index - 1.5) * 4}deg)`,
                    }}
                  >
                    {member.cover_url ? (
                      <CoverImage
                        src={member.cover_url}
                        alt=""
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <TypesetCover
                        title={member.title}
                        seed={member.entry_id}
                      />
                    )}
                  </span>
                ))}
              </div>
              <div className="min-w-0">
                <p className="truncate font-display text-lg font-medium">
                  {row.name}
                </p>
                <p className="text-sm text-muted-foreground">{row.reason}</p>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="rounded-full px-4"
                  disabled={accept.isPending}
                  onClick={() => accept.mutate(row.key)}
                >
                  Make this a shelf
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="rounded-full px-3"
                  disabled={dismiss.isPending}
                  onClick={() => dismiss.mutate(row.key)}
                >
                  Not useful
                </Button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
