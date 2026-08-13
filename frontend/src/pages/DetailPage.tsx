import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import {
  deleteEntry,
  getEntry,
  patchEntry,
  patchItem,
  refreshItem,
  replaceCover,
} from "@/api/library";
import { createShelf, getShelves } from "@/api/shelves";
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
import { Label } from "@/components/ui/label";
import { MetadataDialog } from "@/features/detail/MetadataDialog";
import { OpinionDialog } from "@/features/detail/OpinionDialog";
import { optionalInt, splitList } from "@/features/detail/schemas";
import { statusLabels } from "@/features/library/labels";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/** One term/definition pair, addressable by name instead of by CSS adjacency. */
function Fact({
  name,
  label,
  children,
}: {
  name: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div data-fact={name}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function DetailPage() {
  const entryId = Number(useParams().entryId);
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<
    "opinion" | "metadata" | "refresh" | "delete" | null
  >(null);
  const [error, setError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const detail = useQuery({
    queryKey: ["entry", entryId],
    queryFn: () => getEntry(entryId),
    retry: false,
  });
  const shelves = useQuery({
    queryKey: ["shelves"],
    queryFn: getShelves,
    retry: false,
  });
  const update = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      setError("");
      void cache.invalidateQueries({ queryKey: ["entry", entryId] });
      void cache.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (value: Error) => setError(value.message),
  });

  useEffect(() => {
    if (detail.data) headingRef.current?.focus();
  }, [detail.data]);

  // Focus trapping, initial focus, and Escape-to-close were all hand-rolled
  // here. Radix Dialog owns them now, so the hand-rolled versions are gone
  // rather than left to fight it.

  if (detail.isPending) return <p role="status">Loading book detail…</p>;
  if (!detail.data) return <p role="alert">Book detail could not be loaded</p>;
  const entry = detail.data;
  const item = entry.item;

  async function handleDelete() {
    setDeleteError("");
    try {
      await deleteEntry(entry.id);
      void cache.invalidateQueries({ queryKey: ["library"] });
      toast.success("Book removed from your library");
      navigate("/");
    } catch (e) {
      // Reported inside the dialog, which is still open and still covering the
      // page: an alert rendered behind a modal is an alert nobody sees.
      setDeleteError(
        e instanceof Error ? e.message : "Entry could not be deleted",
      );
    }
  }

  async function handleCreateShelf(name: string) {
    try {
      await createShelf(name);
      void cache.invalidateQueries({ queryKey: ["shelves"] });
      toast.success(`Shelf "${name}" created`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Shelf could not be created");
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <Button variant="ghost" className="px-0" onClick={() => navigate("/")}>
        ← Library
      </Button>
      <div className="mt-8 grid gap-8 md:grid-cols-[240px_1fr]">
        <aside>
          {item.cover_url ? (
            <img
              className="aspect-[2/3] w-full rounded-xl object-cover"
              src={item.cover_url}
              alt={`Cover of ${item.title}`}
            />
          ) : (
            <div
              className="aspect-[2/3] rounded-xl bg-surface-raised"
              role="img"
              aria-label="No cover"
            />
          )}
          <div className="mt-3 block text-sm">
            <Label htmlFor="replace-cover">Replace cover</Label>
            <Input
              id="replace-cover"
              className="mt-1 h-11 py-2"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) update.mutate(() => replaceCover(item.id, file));
              }}
            />
          </div>
        </aside>
        <section>
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="text-4xl font-semibold focus:outline-none"
          >
            {item.title}
          </h1>
          {item.subtitle && (
            <p className="text-lg text-muted-foreground">{item.subtitle}</p>
          )}
          <p className="mt-2 text-foreground">
            {item.sort_author ?? "Unknown author"}
          </p>
          <p className="text-sm text-muted-foreground">
            Edition year: {item.year ?? "unknown"}
            {item.metadata.original_year &&
            item.metadata.original_year !== item.year
              ? ` · Originally published: ${item.metadata.original_year}`
              : ""}
          </p>

          {/* Personal reading region */}
          <section
            className="mt-6 rounded-xl border border-border p-5"
            aria-label="Your reading data"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wider text-primary">
              Your reading data
            </h2>
            <dl className="mt-4 grid grid-cols-2 gap-4">
              <Fact name="status" label="Status">
                {statusLabels[entry.status]}
              </Fact>
              <Fact name="score" label="Score">
                <span
                  className={cn(
                    scoreChipShape,
                    scoreChipClass(entry.score),
                    // Nothing to fill, so nothing to pad: an absent score is a
                    // dash, not an empty chip.
                    entry.score === null && "px-0",
                  )}
                >
                  {entry.score ?? "—"}
                </span>
                {entry.score_provisional && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    (provisional)
                  </span>
                )}
              </Fact>
              <Fact name="started" label="Started">
                {entry.date_started ?? "—"}
              </Fact>
              <Fact name="finished" label="Finished">
                {entry.date_finished ?? "—"}
              </Fact>
              <Fact name="rereads" label="Rereads">
                {entry.reread_count}
              </Fact>
              <Fact name="shelves" label="Shelves">
                {entry.shelves.map((s) => s.name).join(", ") || "—"}
              </Fact>
            </dl>
            {entry.notes && (
              <div className="mt-4">
                <p className="text-xs text-muted-foreground">Notes</p>
                <p className="mt-1 whitespace-pre-wrap text-foreground">
                  {entry.notes}
                </p>
              </div>
            )}
            <div className="mt-5 flex flex-wrap gap-3">
              <Button
                className="rounded-full px-5"
                onClick={() => setDialog("opinion")}
              >
                Edit opinion
              </Button>
              <Button
                variant="outline"
                className="rounded-full border-destructive/60 px-5 text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() => setDialog("delete")}
              >
                Delete entry
              </Button>
            </div>
          </section>

          {/* Edition facts region */}
          <section
            className="mt-6 rounded-xl border border-border p-5"
            aria-label="Edition facts"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wider text-primary">
              Edition facts
            </h2>
            <dl className="mt-4 grid grid-cols-2 gap-4">
              <Fact name="publisher" label="Publisher">
                {item.metadata.publisher || "—"}
              </Fact>
              <Fact name="language" label="Language">
                {item.metadata.language || "—"}
              </Fact>
              <Fact name="pages" label="Pages">
                {item.metadata.page_count ?? "—"}
              </Fact>
              <Fact name="series" label="Series">
                {item.metadata.series || "—"}
              </Fact>
              <Fact name="identifiers" label="Identifiers">
                {Object.entries(item.identifiers).map(([k, v]) => (
                  <span key={k} className="block text-sm">
                    {k}: {v}
                  </span>
                ))}
                {!Object.keys(item.identifiers).length && "—"}
              </Fact>
              <Fact name="sources" label="Sources">
                {item.sources.map((s) => (
                  <span
                    key={`${s.source}:${s.source_id}`}
                    className="block text-sm"
                  >
                    {s.source}
                    {s.is_primary ? " (primary)" : ""}
                  </span>
                ))}
                {!item.sources.length && "—"}
              </Fact>
            </dl>
            {item.metadata.subjects && item.metadata.subjects.length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-muted-foreground">Subjects</p>
                <p className="mt-1 text-foreground">
                  {item.metadata.subjects.join(", ")}
                </p>
              </div>
            )}
            {item.metadata.description && (
              <div className="mt-4">
                <p className="text-xs text-muted-foreground">Description</p>
                <p className="mt-1 whitespace-pre-wrap text-foreground">
                  {item.metadata.description}
                </p>
              </div>
            )}
            <div className="mt-5 flex flex-wrap gap-3">
              <Button
                variant="outline"
                className="rounded-full px-5"
                onClick={() => setDialog("metadata")}
              >
                Edit book metadata
              </Button>
              <Button
                variant="outline"
                className="rounded-full px-5"
                onClick={() => setDialog("refresh")}
              >
                Refresh from provider
              </Button>
            </div>
          </section>
        </section>
      </div>

      <OpinionDialog
        open={dialog === "opinion"}
        onOpenChange={(open) => setDialog(open ? "opinion" : null)}
        entry={entry}
        shelves={shelves.data ?? []}
        onSave={(values) =>
          update
            .mutateAsync(() =>
              patchEntry(entry.id, {
                status: values.status,
                score: values.score,
                notes: values.notes,
                date_started: values.date_started || null,
                date_finished: values.date_finished || null,
                reread_count: Number(values.reread_count || 0),
                shelf_ids: values.shelf_ids,
              }),
            )
            .then(() => undefined)
        }
        onCreateShelf={handleCreateShelf}
      />

      <MetadataDialog
        open={dialog === "metadata"}
        onOpenChange={(open) => setDialog(open ? "metadata" : null)}
        item={item}
        onSave={(values) =>
          update
            .mutateAsync(() =>
              patchItem(item.id, {
                title: values.title.trim(),
                subtitle: values.subtitle || null,
                year: optionalInt(values.year),
                metadata: {
                  ...item.metadata,
                  authors: splitList(values.authors),
                  publisher: values.publisher,
                  language: values.language,
                  page_count: optionalInt(values.page_count),
                  description: values.description || null,
                  subjects: splitList(values.subjects),
                  series: values.series || null,
                  original_year: optionalInt(values.original_year),
                },
              }),
            )
            .then(() => undefined)
        }
      />

      {/* Product spec section 7: confirmation dialogs are limited to delete and
          explicit provider refresh overwrite. */}
      <AlertDialog
        open={dialog === "refresh"}
        onOpenChange={(open) => setDialog(open ? "refresh" : null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Overwrite cached metadata?</AlertDialogTitle>
            <AlertDialogDescription>
              Provider-managed fields will be replaced. Opinion data is
              preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(buttonVariants(), "rounded-full px-5")}
              onClick={() => update.mutate(() => refreshItem(item.id))}
            >
              Confirm refresh
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={dialog === "delete"}
        onOpenChange={(open) => {
          setDialog(open ? "delete" : null);
          if (!open) setDeleteError("");
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Remove this book from your library?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Your score, status, notes, and shelf assignments will be deleted.
              The book metadata and cover remain cached so re-adding is instant.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {deleteError && (
            <p role="alert" className="text-sm text-destructive">
              {deleteError}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(
                buttonVariants({ variant: "destructive" }),
                "rounded-full px-5",
              )}
              onClick={(event) => {
                // Kept open until the request settles, so a failure is
                // reported instead of silently dismissing the dialog.
                event.preventDefault();
                void handleDelete();
              }}
            >
              Delete entry
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {error && (
        <p role="alert" className="mt-4 text-destructive">
          {error}
        </p>
      )}
    </main>
  );
}
