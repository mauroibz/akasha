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
import { CoverImage } from "@/components/CoverImage";
import { TypesetCover } from "@/features/shelves/OpeningCover";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import {
  defaultLibraryFilters,
  mergeUniqueEntries,
} from "@/features/library/library";
import { domainsFrom, formatLabels } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { deleteShelf, getShelves, renameShelf } from "@/api/shelves";
import { getLibraryPage, type ItemType } from "@/api/library";
import type { ShelfWithCount } from "@/api/shelves";
import { countLabel } from "@/features/library/labels";
import { readPinnedShelf, writePinnedShelf } from "@/features/library/library";
import { cn } from "@/lib/utils";
import { queryKeys } from "@/api/keys";
import { Loading } from "@/components/ui/skeleton";

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
    queryKey: queryKeys.shelves,
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
  const queryKey = queryKeys.shelfEntries.list(slug, domainChoice);
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

  const rename = useMutation({
    mutationFn: (name: string) => renameShelf(shelf!.id, name),
    onSuccess: (updated) => {
      setRenaming(false);
      toast.success(`Shelf renamed to "${updated.name}"`);
      void cache.invalidateQueries({ queryKey: queryKeys.shelves });
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
      void cache.invalidateQueries({ queryKey: queryKeys.shelves });
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
        <Loading label="Loading shelf…" shape="page" />
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

  const formatCounts = firstPage?.facets.format_counts ?? {};
  const formatLabelsById = formatLabels(itemTypes.data);

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

      <p className="mt-4 max-w-[44ch] font-display text-xl leading-snug text-foreground/85 md:text-2xl">
        {shelfSentence(shelf, itemTypes.data)}
      </p>
      {Object.keys(formatCounts).length > 0 && (
        <p className="mt-2 text-sm text-muted-foreground">
          {Object.entries(formatCounts)
            .filter(([, n]) => (n ?? 0) > 0)
            .map(
              ([format, count]) =>
                `${formatLabelsById[format] ?? format} ${count}`,
            )
            .join(" · ")}
        </p>
      )}

      {domainsHeld.length > 1 && (
        <div className="mt-6">
          <DomainStrip
            domains={[{ id: everything, label: "Everything" }, ...domainsHeld]}
            value={domainChoice}
            onChange={setDomainChoice}
          />
        </div>
      )}

      {/* Covers without chips over them (Sprint 105): a shelf is for looking at;
          status and score are changed on an entry's own page. */}
      <ul className="mt-10 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {entries.map((entry) => (
          <li key={entry.id}>
            <Link
              to={`/books/${entry.id}`}
              aria-label={`Open ${entry.item.title}`}
              className="group block rounded-md focus-ring"
            >
              <span className="block aspect-[2/3] overflow-hidden rounded-[3px_7px_7px_3px] shadow-[inset_5px_0_0_rgba(0,0,0,0.18),0_16px_26px_-14px_rgba(28,25,23,0.5)] transition-transform duration-300 group-hover:-translate-y-1 motion-reduce:transform-none">
                {entry.item.cover_url ? (
                  <CoverImage
                    src={entry.item.cover_url}
                    alt=""
                    className="h-full w-full object-cover"
                    placeholderClassName="h-full w-full"
                  />
                ) : (
                  <TypesetCover title={entry.item.title} seed={entry.id} />
                )}
              </span>
              <span className="mt-3 block font-display text-lg leading-tight">
                {entry.item.title}
              </span>
            </Link>
            <span className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
              <span className="truncate">{entry.item.creator}</span>
              {entry.score !== null && (
                <span
                  className={cn(
                    scoreChipShape,
                    "ml-auto",
                    scoreChipClass(entry.score),
                  )}
                >
                  {entry.score}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
      {library.hasNextPage && (
        <div className="mt-10 flex justify-center">
          <Button
            variant="outline"
            className="rounded-full px-6"
            disabled={library.isFetchingNextPage}
            onClick={() => void library.fetchNextPage()}
          >
            {library.isFetchingNextPage ? "Loading…" : "Show more"}
          </Button>
        </div>
      )}

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

/**
 * A shelf read back in one sentence (Sprint 105): how many, how many finished,
 * how you rate them. A mixed shelf counts "things", since no one domain's noun
 * is right for it.
 */
function shelfSentence(
  shelf: ShelfWithCount,
  types: ItemType[] | undefined,
): string {
  if (shelf.entry_count === 0)
    return "Nothing on it yet. Add to it from anything's own page.";
  const ids = Object.keys(shelf.members_by_type ?? {});
  const held =
    ids.length === 1
      ? countLabel(shelf.entry_count, ids[0], types)
      : `${shelf.entry_count} things`;
  const parts = [`${held.charAt(0).toUpperCase()}${held.slice(1)}`];
  if (shelf.finished_count) parts.push(`${shelf.finished_count} finished`);
  let sentence = `${parts.join(", ")}.`;
  if (shelf.mean_score != null)
    sentence += ` You rate them ${shelf.mean_score.toFixed(1)}.`;
  return sentence;
}
