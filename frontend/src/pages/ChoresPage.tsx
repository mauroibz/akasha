import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Copy, Image, Inbox, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";

import { getDuplicates } from "@/api/duplicates";
import { getInboxCount, getLibraryPage } from "@/api/library";
import { queryKeys } from "@/api/keys";
import { PageHeader } from "@/components/PageHeader";
import { coverlessFilters, plannedFilters } from "@/features/chores/chores";
import { useItemTypes } from "@/features/library/useItemTypes";

/**
 * The chores the deck does one card at a time (Sprint 112, DEC-176), each with how
 * many cards it holds. A count is the list endpoint's own total for that chore's
 * filter, asked with a page of one.
 */
export function ChoresPage() {
  const itemTypes = useItemTypes();
  const planned = plannedFilters(itemTypes.data);
  const inbox = useQuery({
    queryKey: queryKeys.triage.count,
    queryFn: ({ signal }) => getInboxCount(signal),
  });
  const pile = useQuery({
    queryKey: ["chores", "planned", "count", planned.statuses],
    queryFn: ({ signal }) =>
      getLibraryPage(planned, undefined, signal, 1).then((page) => page.total),
    enabled: itemTypes.isSuccess && planned.statuses.length > 0,
  });
  const coverless = useQuery({
    queryKey: ["chores", "covers", "count"],
    queryFn: ({ signal }) =>
      getLibraryPage(coverlessFilters, undefined, signal, 1).then(
        (page) => page.total,
      ),
  });

  const duplicates = useQuery({
    queryKey: ["chores", "duplicates"],
    queryFn: ({ signal }) => getDuplicates(signal),
  });

  const chores = [
    {
      to: "/inbox/deck",
      title: "Sort the inbox",
      lede: "What an import brought in, filed one at a time.",
      icon: <Inbox aria-hidden="true" />,
      count: inbox.data,
    },
    {
      to: "/deck/planned",
      title: "Still want this?",
      lede: "The planned pile, what has waited longest first. Keep it or let it go.",
      icon: <ListChecks aria-hidden="true" />,
      count: pile.data,
    },
    {
      to: "/deck/covers",
      title: "Find a cover",
      lede: "Everything without a cover, with editions to choose from.",
      icon: <Image aria-hidden="true" />,
      count: coverless.data,
    },
    {
      to: "/deck/duplicates",
      title: "Duplicates",
      lede: "The same work entered twice. Keep one; nothing the other holds is lost.",
      icon: <Copy aria-hidden="true" />,
      count: duplicates.data?.length,
    },
  ];

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-5 py-8">
      <PageHeader
        back
        title="Chores"
        lede="Small jobs, one card at a time. Stop whenever you like."
      />
      <ul aria-label="Chores" className="mt-6 grid gap-3">
        {chores.map((chore) => (
          <li key={chore.to}>
            <Link
              to={chore.to}
              className="group flex items-center gap-4 rounded-xl border border-border bg-surface p-4 transition-colors hover:bg-accent focus-ring"
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary [&_svg]:h-5 [&_svg]:w-5">
                {chore.icon}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{chore.title}</span>
                <span className="block text-sm text-muted-foreground">
                  {chore.lede}
                </span>
              </span>
              {chore.count !== undefined && (
                <span className="font-display text-2xl tabular-nums">
                  {chore.count}
                </span>
              )}
              <ArrowRight
                className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
