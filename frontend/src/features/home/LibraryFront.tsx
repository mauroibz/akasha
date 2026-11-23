import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  getHome,
  getHomeLayout,
  putHomeLayout,
  type HomeLayout,
  type ModuleLayout,
} from "@/api/home";
import { useItemTypes } from "@/features/library/useItemTypes";
import { queryKeys } from "@/api/keys";
import { cn } from "@/lib/utils";

import { ArrangeControls } from "./Arrange";
import { hasContent } from "./content";
import { AddDialog, AddTile, PersonalizeBar } from "./Personalize";
import { Showcase } from "./Showcase";
import { GreetingBar } from "./GreetingBar";
import {
  fallbackLayout,
  isHomeKey,
  isModuleKey,
  labelOf,
  packRows,
  spanClass,
} from "./layout";
import { useArrange } from "./useArrange";

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
  const [arranging, setArranging] = useState(false);
  const [adding, setAdding] = useState(false);
  const arrange = useArrange(layout.modules, layout.save);
  const types = itemTypes.data;
  const data = home.data;
  // Nothing kept yet: the Library's own empty state says what to do first.
  // An answer that is not the front's shape is treated like none: the Library below
  // must never fail because of what sits above it.
  if (!data?.greeting || !Array.isArray(data.now)) return null;
  if (data.greeting.entries === 0 && data.now.length === 0) return null;

  const rows = arranging ? arrange.shown : layout.modules;
  // While personalizing, a thing with nothing to show still stands in its place, so
  // it can be moved and removed; otherwise it is left out until it has something.
  const placed = packRows(
    rows.flatMap((row) =>
      isHomeKey(row.module) &&
      !row.hidden &&
      (arranging || hasContent(row.module, data))
        ? [{ key: row.module, size: row.size }]
        : [],
    ),
  );

  return (
    <section aria-label="Your library today" className="space-y-6 pb-2 pt-6">
      <GreetingBar
        greeting={data.greeting}
        types={types}
        onEdit={() => setArranging((value) => !value)}
        arranging={arranging}
      />
      {arranging && (
        <PersonalizeBar
          onReset={() => layout.save(layout.defaults)}
          onDone={() => setArranging(false)}
          announcement={arrange.announcement}
        />
      )}
      {(placed.length > 0 || arranging) && (
        <div className="grid grid-cols-1 gap-3 min-[720px]:grid-cols-12">
          {placed.map(({ key, size, span }) => {
            const row = rows.find((item) => item.module === key);
            const drawn = hasContent(key, data) ? (
              <Showcase
                moduleKey={key}
                size={size}
                label={labelOf(row ?? { module: key })}
                data={data}
                types={types}
              />
            ) : null;
            return (
              <div
                key={key}
                ref={arranging ? arrange.box(key) : undefined}
                data-module={key}
                data-family={isModuleKey(key) ? undefined : key.split(":")[0]}
                className={cn(
                  "min-w-0",
                  spanClass[span],
                  arranging
                    ? "rounded-xl outline-dashed outline-2 outline-offset-4 outline-primary/60"
                    : "[&>section]:h-full",
                  arrange.dragging === key && "opacity-70",
                )}
              >
                {arranging && row ? (
                  <ArrangeControls row={row} arrange={arrange} />
                ) : null}
                {drawn ??
                  (arranging ? (
                    // One line, not a box: an empty thing should not cost a
                    // screen of scrolling while the page is being arranged.
                    <p className="px-3 pb-2 text-xs text-muted-foreground">
                      Nothing to show in it yet; it appears when it has
                      something.
                    </p>
                  ) : null)}
              </div>
            );
          })}
          {/* The one way to add (Sprint 150): a blank square where the next would go. */}
          {arranging && (
            <div className="min-w-0 min-[720px]:col-span-3">
              <AddTile onClick={() => setAdding(true)} />
            </div>
          )}
        </div>
      )}
      <AddDialog
        open={adding}
        onOpenChange={setAdding}
        layout={rows}
        types={types}
        onAdd={arrange.add}
      />
      {/* What follows is the whole library: said once, so the showcases above do
          not read as its first rows. */}
      <h2 className="pt-2 font-display text-xl font-medium">Everything</h2>
    </section>
  );
}
