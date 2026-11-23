import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getHome, type Home } from "@/api/home";
import { queryKeys } from "@/api/keys";
import { Loading } from "@/components/ui/skeleton";
import { useItemTypes } from "@/features/library/useItemTypes";

import { GreetingBar } from "./GreetingBar";
import { defaultLayout, spanClass, type ModuleKey } from "./layout";
import { LibraryTiles } from "./LibraryTiles";
import { OnNow } from "./OnNow";
import { UpNext } from "./UpNext";
import { localDate } from "./year";
import { YearModule } from "./YearModule";

function isEmpty(home: Home): boolean {
  return home.greeting.entries === 0 && home.now.length === 0;
}

/**
 * Home (Sprint 130, DEC-183): the screen Akasha opens on. A 12-column grid of
 * modules — what is under way, what is next, the year, every library — all drawn
 * from one `GET /api/home` that reads stored data only.
 */
export function HomePage() {
  const itemTypes = useItemTypes();
  const home = useQuery({
    queryKey: queryKeys.home,
    queryFn: ({ signal }) => getHome(signal),
    staleTime: 30_000,
  });
  const types = itemTypes.data;

  let body;
  if (home.isPending) {
    body = <Loading label="Opening Home…" shape="page" />;
  } else if (home.isError) {
    body = (
      <p role="alert" className="text-sm text-destructive">
        {home.error instanceof Error
          ? home.error.message
          : "Home could not be loaded"}
        .{" "}
        <button
          type="button"
          className="underline focus-ring"
          onClick={() => void home.refetch()}
        >
          Try again
        </button>
      </p>
    );
  } else if (isEmpty(home.data)) {
    body = (
      <div className="space-y-6">
        <GreetingBar greeting={home.data.greeting} types={types} />
        <section className="rounded-xl border border-border bg-surface p-6">
          <h2 className="font-display text-2xl font-medium">
            Your desk is ready
          </h2>
          <p className="mt-2 max-w-prose text-sm text-muted-foreground">
            Home shows what you are in the middle of, what comes next and your
            whole library at a glance. It fills in as soon as there is something
            in it.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link
              to="/add"
              className="inline-flex min-h-11 items-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground focus-ring"
            >
              Add something
            </Link>
            <Link
              to="/import"
              className="inline-flex min-h-11 items-center rounded-full border border-border px-5 text-sm font-medium focus-ring"
            >
              Import a library
            </Link>
          </div>
        </section>
      </div>
    );
  } else {
    const data = home.data;
    const modules: Record<ModuleKey, (className: string) => React.ReactNode> = {
      now: (className) => (
        <OnNow entries={data.now} types={types} className={className} />
      ),
      next: (className) => (
        <UpNext
          picks={data.next}
          pile={data.greeting.pile}
          types={types}
          className={className}
        />
      ),
      year: (className) => (
        <YearModule
          year={data.year}
          types={types}
          today={localDate(data.greeting.today)}
          className={className}
        />
      ),
      libraries: (className) =>
        data.domains.length ? (
          <LibraryTiles
            tiles={data.domains}
            types={types}
            className={className}
          />
        ) : null,
    };
    body = (
      <div className="space-y-4">
        <GreetingBar greeting={data.greeting} types={types} />
        <div className="grid grid-cols-1 gap-3 min-[720px]:grid-cols-12">
          {defaultLayout.map(({ key, span }) => (
            <div
              key={key}
              className={`min-w-0 ${spanClass[span]} [&>section]:h-full`}
            >
              {modules[key]("")}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <main aria-label="Home" className="mx-auto max-w-7xl px-4 py-5 sm:px-6">
      {body}
    </main>
  );
}
