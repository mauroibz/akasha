import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { DomainStrip } from "@/components/DomainStrip";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Input } from "@/components/ui/input";
import { VirtualLibrary } from "@/features/library/VirtualLibrary";
import {
  defaultLibraryFilters,
  mergeUniqueEntries,
} from "@/features/library/library";
import {
  domainsFrom,
  formatLabels,
  statusLabels,
} from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { deleteShelf, getShelves, renameShelf } from "@/api/shelves";
import { getLibraryPage, patchEntry, type LibraryEntry } from "@/api/library";
import { readPinnedShelf, writePinnedShelf } from "@/features/library/library";
import { cn } from "@/lib/utils";

const everything = "";

/**
 * A shelf, whole (Sprint 074 deliverable 5, proposal §3.3.3) — the set the owner
 * assembled by hand, across every domain it holds, not the one-domain-at-a-time
 * question the library answers (DEC-065). `/triage` and the export are the
 * standing precedent for a screen that spans domains; this is the second one,
 * accepted by the owner in DEC-139.
 *
 * Deliberately narrow: no search, no sort, no provider access of its own
 * (non-scope) — the domain strip is the only control besides the ordinary
 * entry actions the library grid already carries. If this page starts growing
 * those, it has become a second library, which is exactly the drift DEC-139's
 * acceptance warned against.
 */
export function ShelfPage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const cache = useQueryClient();
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, [slug]);

  const itemTypes = useItemTypes();
  const domains = useMemo(() => domainsFrom(itemTypes.data), [itemTypes.data]);

  const shelvesQuery = useQuery({
    queryKey: ["shelves"],
    queryFn: getShelves,
    retry: false,
  });
  const shelf = shelvesQuery.data?.find((row) => row.slug === slug);

  const [domainChoice, setDomainChoice] = useState(everything);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [pinnedSlug, setPinnedSlug] = useState(
    () => readPinnedShelf()?.slug ?? null,
  );

  const domainsHeld = useMemo(
    () =>
      shelf
        ? domains.filter(
            (domain) => (shelf.members_by_type?.[domain.id] ?? 0) > 0,
          )
        : [],
    [domains, shelf],
  );

  const filters = useMemo(
    () => ({
      ...defaultLibraryFilters,
      shelves: slug ? [slug] : [],
      types: domainChoice ? [domainChoice] : [],
    }),
    [slug, domainChoice],
  );
  const queryKey = ["shelf-entries", slug, domainChoice] as const;
  const library = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam, signal }) =>
      getLibraryPage(filters, pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(slug),
    retry: false,
  });
  const entries = useMemo(
    () =>
      mergeUniqueEntries(library.data?.pages.map((page) => page.items) ?? []),
    [library.data],
  );
  const firstPage = library.data?.pages[0];

  const mutation = useMutation({
    mutationFn: ({
      entry,
      changes,
    }: {
      entry: LibraryEntry;
      changes: Partial<Pick<LibraryEntry, "score" | "status">>;
    }) => patchEntry(entry.id, changes),
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: ["shelf-entries", slug] });
    },
    onError: () => {
      toast.error("Your change could not be saved");
    },
  });

  const rename = useMutation({
    mutationFn: (name: string) => renameShelf(shelf!.id, name),
    onSuccess: (updated) => {
      setRenaming(false);
      toast.success(`Shelf renamed to "${updated.name}"`);
      void cache.invalidateQueries({ queryKey: ["shelves"] });
      navigate(`/shelves/${encodeURIComponent(updated.slug)}`, {
        replace: true,
      });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: () => deleteShelf(shelf!.id),
    onSuccess: () => {
      toast.success("Shelf deleted", {
        description: "Your entries are retained.",
      });
      if (pinnedSlug === slug) {
        writePinnedShelf(null);
        setPinnedSlug(null);
      }
      void cache.invalidateQueries({ queryKey: ["shelves"] });
      navigate("/shelves");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const pinned = pinnedSlug === slug;
  const togglePin = () => {
    if (!shelf) return;
    if (pinned) {
      writePinnedShelf(null);
      setPinnedSlug(null);
    } else {
      writePinnedShelf({ slug: shelf.slug, name: shelf.name });
      setPinnedSlug(shelf.slug);
    }
  };

  if (shelvesQuery.isPending) {
    return (
      <main className="mx-auto min-h-screen max-w-[1600px] px-5 py-8">
        <p role="status" className="text-muted-foreground">
          Loading shelf…
        </p>
      </main>
    );
  }

  if (!shelf) {
    return (
      <main className="mx-auto min-h-screen max-w-[1600px] px-5 py-8">
        <PageHeader title="Shelf not found" />
        <p className="mt-4 text-muted-foreground">
          This shelf may have been deleted.{" "}
          <Link to="/shelves" className="text-primary underline">
            Back to shelves
          </Link>
        </p>
      </main>
    );
  }

  const statusCounts = firstPage?.facets.status_counts ?? {};
  const statusEntries = Object.entries(statusCounts).filter(
    ([, n]) => (n ?? 0) > 0,
  );
  const statusTotal = statusEntries.reduce((sum, [, n]) => sum + (n ?? 0), 0);
  const formatCounts = firstPage?.facets.format_counts ?? {};
  const formatLabelsById = formatLabels(itemTypes.data);
  const scored = entries.filter((entry) => entry.score !== null);
  const meanScore =
    scored.length > 0
      ? scored.reduce((sum, entry) => sum + (entry.score ?? 0), 0) /
        scored.length
      : null;

  return (
    <main className="mx-auto min-h-screen max-w-[1600px] px-5 py-8">
      <Link
        to="/shelves"
        className="focus-ring inline-flex min-h-11 items-center text-sm font-medium hover:text-primary"
      >
        ← Shelves
      </Link>
      <PageHeader
        headingRef={headingRef}
        title={shelf.name}
        className="mt-2"
        actions={
          <>
            <Button
              variant="outline"
              className="h-11 rounded-full aria-pressed:border-primary aria-pressed:text-primary"
              aria-pressed={pinned}
              onClick={togglePin}
            >
              {pinned ? "Pinned" : "Pin to library"}
            </Button>
            <Button
              variant="outline"
              className="h-11 rounded-full"
              onClick={() => {
                setRenaming(true);
                setRenameValue(shelf.name);
              }}
            >
              Rename
            </Button>
            <Button
              variant="outline"
              className="h-11 rounded-full border-destructive/60 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setDeleting(true)}
            >
              Delete
            </Button>
          </>
        }
      />

      <div className="mt-6 flex flex-wrap items-end gap-6">
        <p className="text-3xl font-semibold tabular-nums">
          {shelf.entry_count}
        </p>
        {statusTotal > 0 && (
          <div className="flex min-w-[200px] flex-col gap-1.5">
            <div
              aria-hidden="true"
              className="flex h-2.5 overflow-hidden rounded-full bg-surface-raised"
            >
              {statusEntries.map(([status, count], index) => (
                <div
                  key={status}
                  style={{
                    width: `${((count ?? 0) / statusTotal) * 100}%`,
                    opacity: Math.max(1 - index * 0.18, 0.25),
                  }}
                  className="h-full bg-primary"
                />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              {/* A shelf can span domains that disagree about their status
                  vocabulary, so this reads the shared fallback labels rather
                  than one domain's own (`statusLabelFor` needs exactly one
                  domain to resolve against, which a mixed shelf does not
                  have). */}
              {statusEntries
                .map(
                  ([status, count]) =>
                    `${count} ${(statusLabels[status as keyof typeof statusLabels] ?? status).toLowerCase()}`,
                )
                .join(" · ")}
            </p>
          </div>
        )}
        {meanScore !== null && (
          <div>
            <p className="text-xs text-muted-foreground">Mean score</p>
            <p className="text-lg font-semibold tabular-nums">
              {meanScore.toFixed(1)}
            </p>
          </div>
        )}
        {Object.keys(formatCounts).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground">Formats</p>
            <p className="text-sm">
              {Object.entries(formatCounts)
                .filter(([, n]) => (n ?? 0) > 0)
                .map(
                  ([format, count]) =>
                    `${formatLabelsById[format] ?? format} ${count}`,
                )
                .join(" · ")}
            </p>
          </div>
        )}
      </div>

      {domainsHeld.length > 1 && (
        <div className="mt-6">
          <DomainStrip
            domains={[{ id: everything, label: "Everything" }, ...domainsHeld]}
            value={domainChoice}
            onChange={setDomainChoice}
          />
        </div>
      )}

      <div className="mt-6">
        <VirtualLibrary
          entries={entries}
          total={firstPage?.total ?? entries.length}
          hasNextPage={Boolean(library.hasNextPage)}
          isFetchingNextPage={library.isFetchingNextPage}
          focusedId={null}
          loadNextPage={() => void library.fetchNextPage()}
          onFocusEntry={() => {}}
          onScore={(entry, score) =>
            mutation.mutate({ entry, changes: { score } })
          }
          onStatus={(entry, status) =>
            mutation.mutate({ entry, changes: { status } })
          }
          view="grid"
        />
      </div>

      <AlertDialog
        open={renaming}
        onOpenChange={(open) => !open && setRenaming(false)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rename shelf</AlertDialogTitle>
          </AlertDialogHeader>
          <Input
            className="h-11"
            aria-label={`New name for ${shelf.name}`}
            value={renameValue}
            autoFocus
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && renameValue.trim()) {
                e.preventDefault();
                rename.mutate(renameValue.trim());
              }
            }}
          />
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(buttonVariants({}), "rounded-full px-5")}
              onClick={(e) => {
                e.preventDefault();
                if (renameValue.trim()) rename.mutate(renameValue.trim());
              }}
            >
              Save
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={deleting}
        onOpenChange={(open) => !open && setDeleting(false)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete &ldquo;{shelf.name}&rdquo;?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This shelf will be removed from everything on it. The entries
              themselves are retained and remain in your library.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(
                buttonVariants({ variant: "destructive" }),
                "rounded-full px-5",
              )}
              onClick={() => remove.mutate()}
            >
              Delete shelf
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}
