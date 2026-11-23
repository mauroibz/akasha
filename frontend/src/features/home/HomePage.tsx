import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import {
  getHome,
  getHomeLayout,
  putHomeLayout,
  type Home,
  type HomeLayout,
  type ModuleLayout,
  type ModuleSize,
} from "@/api/home";
import { queryKeys } from "@/api/keys";
import { Loading } from "@/components/ui/skeleton";
import { useItemTypes } from "@/features/library/useItemTypes";

import { EditHome } from "./EditHome";
import { GreetingBar } from "./GreetingBar";
import {
  fallbackLayout,
  isModuleKey,
  packRows,
  spanClass,
  type ModuleKey,
} from "./layout";
import { Lately } from "./Lately";
import { LentOut } from "./LentOut";
import { LibraryTiles } from "./LibraryTiles";
import { OnNow } from "./OnNow";
import { QuestionModule } from "./QuestionModule";
import { ShelvesModule } from "./ShelvesModule";
import { SuggestedModule } from "./SuggestedModule";
import { TidyUp } from "./TidyUp";
import { UpNext } from "./UpNext";
import { localDate } from "./year";
import { YearModule } from "./YearModule";

function isEmpty(home: Home): boolean {
  return home.greeting.entries === 0 && home.now.length === 0;
}

/**
 * The stored layout, saved as it is edited. Until it arrives, or when it cannot be
 * read, the default stands in, so Home never waits on its own arrangement.
 */
function useLayout() {
  const queryClient = useQueryClient();
  const layout = useQuery({
    queryKey: queryKeys.homeLayout,
    queryFn: ({ signal }) => getHomeLayout(signal),
    staleTime: Infinity,
    retry: false,
  });
  const save = useMutation({
    mutationFn: putHomeLayout,
    // One at a time, in the order made, so a quick run of edits is stored as the
    // last of them rather than whichever request the server answered last.
    scope: { id: "home-layout" },
    onSuccess: () => {
      // A module shown again has to be read; one hidden is no longer read.
      void queryClient.invalidateQueries({ queryKey: queryKeys.home });
    },
    onError: (error) => {
      // Show what the server holds rather than an edit it refused.
      void queryClient.invalidateQueries({ queryKey: queryKeys.homeLayout });
      toast.error(
        error instanceof Error
          ? error.message
          : "Your layout could not be saved",
      );
    },
  });
  return {
    modules: layout.data?.modules ?? fallbackLayout,
    defaults: layout.data?.defaults ?? fallbackLayout,
    save: (modules: ModuleLayout[]) => {
      // Shown at once; the request follows in the background.
      void queryClient.cancelQueries({ queryKey: queryKeys.homeLayout });
      queryClient.setQueryData<HomeLayout>(queryKeys.homeLayout, (before) => ({
        modules,
        defaults: before?.defaults ?? fallbackLayout,
      }));
      save.mutate(modules);
    },
  };
}

/** Whether a module has anything to show; one with nothing is hidden until it has. */
function hasContent(key: ModuleKey, home: Home): boolean {
  switch (key) {
    case "year":
      return home.year !== null;
    case "lately":
      return Boolean(home.lately?.length);
    case "libraries":
      return home.domains.length > 0;
    case "tidy":
      return Boolean(
        home.tidy &&
        home.tidy.duplicates + home.tidy.without_cover + home.tidy.unscored,
      );
    case "question":
      return home.question !== null;
    case "shelves":
      return Boolean(home.shelves?.length);
    case "lent":
      return Boolean(home.lent?.total);
    case "suggested":
      return Boolean(home.suggested?.length);
    default:
      return true;
  }
}

/**
 * Home (Sprints 130-131, DEC-183): the screen Akasha opens on. A 12-column grid of
 * modules — what is under way, what is next, the year, what happened lately, every
 * library, small jobs, one question, shelves and loans — all drawn from one
 * `GET /api/home` that reads stored data only, in the order, sizes and visibility
 * the person chose in *Edit home*.
 */
export function HomePage() {
  const itemTypes = useItemTypes();
  const home = useQuery({
    queryKey: queryKeys.home,
    queryFn: ({ signal }) => getHome(signal),
    staleTime: 30_000,
  });
  const layout = useLayout();
  const [editing, setEditing] = useState(false);
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
    const modules: Record<ModuleKey, (size: ModuleSize) => React.ReactNode> = {
      now: (size) => <OnNow entries={data.now} types={types} size={size} />,
      next: (size) => (
        <UpNext
          picks={data.next}
          pile={data.greeting.pile}
          types={types}
          size={size}
        />
      ),
      year: () =>
        data.year ? (
          <YearModule
            year={data.year}
            types={types}
            today={localDate(data.greeting.today)}
          />
        ) : null,
      lately: (size) => <Lately rows={data.lately ?? []} size={size} />,
      libraries: () => <LibraryTiles tiles={data.domains} types={types} />,
      tidy: () =>
        data.tidy ? <TidyUp tidy={data.tidy} types={types} /> : null,
      question: () =>
        data.question ? (
          <QuestionModule question={data.question} types={types} />
        ) : null,
      shelves: (size) => (
        <ShelvesModule shelves={data.shelves ?? []} size={size} />
      ),
      lent: (size) =>
        data.lent ? <LentOut lent={data.lent} size={size} /> : null,
      suggested: (size) => (
        <SuggestedModule
          suggestions={data.suggested ?? []}
          types={types}
          size={size}
        />
      ),
    };
    const placed = packRows(
      layout.modules.flatMap((row) =>
        isModuleKey(row.module) && !row.hidden && hasContent(row.module, data)
          ? [{ key: row.module, size: row.size }]
          : [],
      ),
    );
    body = (
      <div className="space-y-4">
        <GreetingBar
          greeting={data.greeting}
          types={types}
          onEdit={() => setEditing(true)}
        />
        <div className="grid grid-cols-1 gap-3 min-[720px]:grid-cols-12">
          {placed.map(({ key, size, span }) => (
            <div
              key={key}
              data-module={key}
              className={`min-w-0 ${spanClass[span]} [&>section]:h-full`}
            >
              {modules[key](size)}
            </div>
          ))}
        </div>
        <EditHome
          open={editing}
          onOpenChange={setEditing}
          layout={layout.modules}
          defaults={layout.defaults}
          onChange={layout.save}
        />
      </div>
    );
  }

  return (
    <main aria-label="Home" className="mx-auto max-w-7xl px-4 py-5 sm:px-6">
      {body}
    </main>
  );
}
