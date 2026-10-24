import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Copy, Image, Inbox } from "lucide-react";
import { Link } from "react-router-dom";

import { getDuplicates } from "@/api/duplicates";
import { getInboxCount, getLibraryPage } from "@/api/library";
import { queryKeys } from "@/api/keys";
import { PageHeader } from "@/components/PageHeader";
import { coverlessFilters } from "@/features/chores/chores";

/**
 * Tidy up: the upkeep the deck does one card at a time (Sprint 112, DEC-176; named
 * and narrowed in Sprint 125, DEC-179), each with how many cards it holds. A count
 * is the list endpoint's own total for that chore's filter, asked with a page of one.
 */
export function ChoresPage() {
  const inbox = useQuery({
    queryKey: queryKeys.triage.count,
    queryFn: ({ signal }) => getInboxCount(signal),
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

  // Upkeep only (Sprint 125, DEC-179): the questions about your taste moved to
  // the top of Insights as games, and this page keeps the jobs that are jobs.
  const chores = [
    {
      to: "/inbox/deck",
      title: "Sort the inbox",
      lede: "What an import brought in, filed one at a time.",
      icon: <Inbox aria-hidden="true" />,
      count: inbox.data,
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
        back={{ to: "/settings", label: "Settings" }}
        title="Tidy up"
        lede="Small jobs, one card at a time. Stop whenever you like."
      />
      <ul aria-label="Tidy up" className="mt-6 grid gap-3">
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
      <p className="mt-8 text-sm text-muted-foreground">
        Looking for the games, like which of your 8s is best?{" "}
        <Link
          to="/insights"
          className="inline-flex min-h-11 items-center font-medium text-primary-text underline-offset-4 hover:underline focus-ring"
        >
          They're at the top of Insights
        </Link>
      </p>
    </main>
  );
}
