import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { queryKeys } from "@/api/keys";
import { getLoans, updateLoan } from "@/api/loans";
import { CoverImage } from "@/components/CoverImage";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/ui/empty-state";
import { Loading } from "@/components/ui/skeleton";
import { howLong, readableDay } from "@/features/house/house";
import { localDay } from "@/features/progress/outline";

/**
 * What is out (Sprint 111, DEC-176): a quiet list, longest out first, each with who
 * has it and since when, and one tap for its return. Opened from its ledge on
 * Shelves (Sprint 122), the command bar and a detail page's *Lent* row.
 */
export function LentPage() {
  const queryClient = useQueryClient();
  const loans = useQuery({
    queryKey: queryKeys.loans,
    queryFn: ({ signal }) => getLoans(true, signal),
  });
  const back = useMutation({
    mutationFn: (loanId: number) =>
      updateLoan(loanId, { returned_on: localDay(new Date()) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.loans });
      void queryClient.invalidateQueries({ queryKey: queryKeys.library.all });
    },
  });
  const rows = Array.isArray(loans.data) ? loans.data : [];
  const today = new Date();

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-5 py-8">
      <PageHeader
        back={{ to: "/shelves", label: "Shelves" }}
        title="Lent out"
        lede="What other people have, and since when."
        count={rows.length || undefined}
      />
      {loans.isPending ? (
        <Loading label="Loading what is lent…" />
      ) : rows.length === 0 ? (
        <EmptyState title="Nothing is lent out">
          Lend something from its page, under <em>Lent</em>.
        </EmptyState>
      ) : (
        <ul className="mt-6 divide-y divide-border">
          {rows.map((loan) => (
            <li key={loan.id} className="flex items-center gap-4 py-4">
              <Link
                to={`/books/${loan.entry.id}`}
                className="w-12 shrink-0 focus-ring"
                aria-label={`Open ${loan.entry.item.title}`}
              >
                <CoverImage
                  src={loan.entry.item.cover_url ?? null}
                  alt=""
                  className="aspect-[2/3] w-12 rounded object-cover"
                />
              </Link>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{loan.entry.item.title}</p>
                <p className="text-sm text-muted-foreground">
                  <span className="text-foreground">{loan.person}</span> ·{" "}
                  {readableDay(loan.lent_on)} · {howLong(loan.lent_on, today)}
                </p>
              </div>
              <button
                type="button"
                aria-label={`${loan.entry.item.title} is back`}
                disabled={back.isPending}
                onClick={() => back.mutate(loan.id)}
                className="shrink-0 rounded-full bg-primary/15 px-4 py-2 text-sm font-medium text-primary focus-ring hover:bg-primary/25"
              >
                It's back
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
