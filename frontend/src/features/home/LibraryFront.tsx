import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
import { useItemTypes } from "@/features/library/useItemTypes";
import { queryKeys } from "@/api/keys";

import { EditHome } from "./EditHome";
import { GreetingBar } from "./GreetingBar";
import { Lately } from "./Lately";
import {
  fallbackLayout,
  isHomeKey,
  isModuleKey,
  packRows,
  spanClass,
  type HomeKey,
} from "./layout";
import { LibraryYear } from "./LibraryYear";
import { OnNow } from "./OnNow";
import { QuestionModule } from "./QuestionModule";
import { ShelfModule } from "./ShelfModule";
import { SuggestedModule } from "./SuggestedModule";
import { UpNext } from "./UpNext";
import { localDate } from "./year";

/**
 * The stored layout, saved as it is edited. Until it arrives, or when it cannot be
 * read, the default stands in, so the Library never waits on its own arrangement.
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
      // A showcase shown again has to be read; one hidden is no longer read.
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

/** Whether a showcase has anything to show; one with nothing is left out until it has. */
function hasContent(key: HomeKey, home: Home): boolean {
  if (key.startsWith("year:"))
    return (home.library_years ?? []).some(
      (row) => `year:${row.item_type}` === key,
    );
  if (key.startsWith("shelf:"))
    return (home.shelf_modules ?? []).some((row) => `shelf:${row.id}` === key);
  if (key === "next") return home.next.length > 0;
  if (key === "question") return home.question !== null;
  if (key === "suggested") return Boolean(home.suggested?.length);
  return false;
}

/**
 * The front of the Library (Sprint 141, DEC-193): the greeting, what is under way,
 * what happened lately, and the showcases the person placed, above the grid. It is
 * what Home was (Sprints 130-138), without the modules that repeated the Library.
 *
 * All of it comes from one `GET /api/home` that reads stored data only. The grid
 * below does not wait for it: until the answer arrives, and if it never does, this
 * draws nothing and the Library is the Library.
 */
export function LibraryFront() {
  const itemTypes = useItemTypes();
  const home = useQuery({
    queryKey: queryKeys.home,
    queryFn: ({ signal }) => getHome(signal),
    staleTime: 30_000,
  });
  const layout = useLayout();
  const [editing, setEditing] = useState(false);
  const types = itemTypes.data;
  const data = home.data;
  // Nothing kept yet: the Library's own empty state says what to do first.
  // An answer that is not the front's shape is treated like none: the Library below
  // must never fail because of what sits above it.
  if (!data?.greeting || !Array.isArray(data.now)) return null;
  if (data.greeting.entries === 0 && data.now.length === 0) return null;

  const today = localDate(data.greeting.today);
  const render = (key: HomeKey, size: ModuleSize): React.ReactNode => {
    if (key === "next")
      return (
        <UpNext
          picks={data.next}
          pile={data.greeting.pile}
          types={types}
          size={size}
        />
      );
    if (key === "question")
      return data.question ? (
        <QuestionModule question={data.question} types={types} />
      ) : null;
    if (key === "suggested")
      return (
        <SuggestedModule
          suggestions={data.suggested ?? []}
          types={types}
          size={size}
        />
      );
    const year = (data.library_years ?? []).find(
      (row) => `year:${row.item_type}` === key,
    );
    if (year)
      return (
        <LibraryYear year={year} types={types} size={size} today={today} />
      );
    const shelf = (data.shelf_modules ?? []).find(
      (row) => `shelf:${row.id}` === key,
    );
    return shelf ? <ShelfModule shelf={shelf} size={size} /> : null;
  };
  const placed = packRows(
    layout.modules.flatMap((row) =>
      isHomeKey(row.module) && !row.hidden && hasContent(row.module, data)
        ? [{ key: row.module, size: row.size }]
        : [],
    ),
  );

  return (
    <section aria-label="Your library today" className="space-y-6 pb-2 pt-6">
      <GreetingBar
        greeting={data.greeting}
        types={types}
        onEdit={() => setEditing(true)}
      />
      {data.now.length > 0 && (
        <OnNow entries={data.now} types={types} size="L" />
      )}
      <Lately rows={data.lately ?? []} />
      {placed.length > 0 && (
        <div className="grid grid-cols-1 gap-3 min-[720px]:grid-cols-12">
          {placed.map(({ key, size, span }) => (
            <div
              key={key}
              data-module={key}
              data-family={isModuleKey(key) ? undefined : key.split(":")[0]}
              className={`min-w-0 ${spanClass[span]} [&>section]:h-full`}
            >
              {render(key, size)}
            </div>
          ))}
        </div>
      )}
      {/* What follows is the whole library: said once, so the showcases above do
          not read as its first rows. */}
      <h2 className="pt-2 font-display text-xl font-medium">Everything</h2>
      <EditHome
        open={editing}
        onOpenChange={setEditing}
        layout={layout.modules}
        defaults={layout.defaults}
        onChange={layout.save}
      />
    </section>
  );
}
