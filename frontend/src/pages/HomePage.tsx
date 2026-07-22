import { useQuery } from "@tanstack/react-query";

import { getLibraryPage, type LibraryFilters } from "@/api/library";

const defaultFilters: LibraryFilters = {
  statuses: [],
  shelves: [],
  query: "",
  sort: "date_added",
  order: "desc",
};

export function HomePage() {
  const library = useQuery({
    queryKey: ["library", defaultFilters],
    queryFn: () => getLibraryPage(defaultFilters),
    retry: false,
  });
  return (
    <main className="mx-auto min-h-screen max-w-7xl px-6 py-8">
      <header className="flex items-end justify-between border-b border-zinc-800 pb-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-fuchsia-400">
            Personal library
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Akasha</h1>
        </div>
        {library.data && (
          <p className="text-sm text-zinc-400">
            Inbox {library.data.facets.status_counts.unsorted ?? 0}
          </p>
        )}
      </header>
      {library.isPending && (
        <div className="py-24 text-center text-zinc-400" aria-live="polite" role="status">
          Loading your library…
        </div>
      )}
      {library.isError && (
        <div className="py-24 text-center" role="alert">
          <h2 className="text-xl font-semibold">Your library could not be loaded</h2>
          <button
            className="mt-5 min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fuchsia-300"
            onClick={() => void library.refetch()}
          >
            Try again
          </button>
        </div>
      )}
      {library.data?.items.length === 0 && (
        <section className="py-24 text-center">
          <h2 className="text-2xl font-semibold">Your library is waiting</h2>
          <p className="mt-2 text-zinc-400">Add a book or visit the inbox to get started.</p>
        </section>
      )}
      {library.data && library.data.items.length > 0 && (
        <section aria-label="Library" className="grid grid-cols-2 gap-6 py-8 sm:grid-cols-3 lg:grid-cols-5">
          {library.data.items.map((entry) => (
            <article key={entry.id} className="min-w-0">
              <div className="aspect-[2/3] rounded-xl bg-zinc-900" />
              <h2 className="mt-3 truncate font-semibold">{entry.item.title}</h2>
              <p className="mt-1 truncate text-sm text-zinc-400">
                {entry.item.sort_author ?? "Unknown author"}
              </p>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
