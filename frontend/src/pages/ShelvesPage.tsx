import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { CoverImage } from "@/components/CoverImage";
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
import { Input } from "@/components/ui/input";
import { buttonVariants } from "@/components/ui/button-variants";
import { CoverStack } from "@/features/library/InsightsRanking";
import { magnitude, weightClass } from "@/features/library/insights";
import { cn } from "@/lib/utils";
import {
  createShelf,
  deleteShelf,
  getShelves,
  renameShelf,
  type ShelfWithCount,
} from "@/api/shelves";

export function ShelvesPage() {
  const cache = useQueryClient();
  const [newName, setNewName] = useState("");
  const [error, setError] = useState("");
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingShelf, setDeletingShelf] = useState<ShelfWithCount | null>(
    null,
  );
  const headingRef = useRef<HTMLHeadingElement>(null);

  const shelves = useQuery({
    queryKey: ["shelves"],
    queryFn: getShelves,
    retry: false,
  });

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const create = useMutation({
    mutationFn: (name: string) => createShelf(name),
    onSuccess: (_data, name) => {
      setError("");
      setNewName("");
      toast.success(`Shelf "${name}" created`);
      void cache.invalidateQueries({ queryKey: ["shelves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const rename = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      renameShelf(id, name),
    onSuccess: (_data, { name }) => {
      setRenamingId(null);
      setError("");
      toast.success(`Shelf renamed to "${name}"`);
      void cache.invalidateQueries({ queryKey: ["shelves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteShelf(id),
    onSuccess: () => {
      setDeletingShelf(null);
      toast.success("Shelf deleted", {
        description: "Your entries are retained.",
      });
      void cache.invalidateQueries({ queryKey: ["shelves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-5 py-8">
      <PageHeader
        back
        headingRef={headingRef}
        title="Shelves"
        lede="Organize your library with custom shelves. Deleting a shelf removes the tag from what is on it, but never deletes anything itself."
      />

      {/* Create shelf */}
      <section className="mt-6 flex gap-2">
        <Input
          className="h-11 flex-1"
          aria-label="New shelf name"
          placeholder="New shelf name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && newName.trim()) {
              e.preventDefault();
              create.mutate(newName.trim());
            }
          }}
        />
        <Button
          className="rounded-full px-5"
          disabled={!newName.trim() || create.isPending}
          onClick={() => create.mutate(newName.trim())}
        >
          Create shelf
        </Button>
      </section>

      {error && (
        <p role="alert" className="mt-4 text-destructive">
          {error}
        </p>
      )}

      {/* Shelf list */}
      {shelves.isPending && (
        <p role="status" className="mt-8 text-muted-foreground">
          Loading shelves…
        </p>
      )}
      {shelves.isError && (
        <p role="alert" className="mt-8 text-destructive">
          Shelves could not be loaded
        </p>
      )}
      {shelves.data && shelves.data.length === 0 && (
        <p className="mt-8 text-muted-foreground">
          No shelves yet. Create one above.
        </p>
      )}
      {shelves.data && shelves.data.length > 0 && (
        <ul className="mt-6 space-y-3">
          {(() => {
            // Every row's bar reads against the same leader, so proportion is
            // seen rather than computed (deliverable 2, the insights ranking's
            // own rule). A single shelf's own count is never its own ceiling.
            const max = Math.max(
              ...shelves.data.map((row) => row.entry_count),
              1,
            );
            return shelves.data.map((shelf) => {
              const share = magnitude(shelf.entry_count, max);
              const covers = shelf.covers ?? [];
              return (
                <li
                  key={shelf.id}
                  className="relative flex items-center gap-3 overflow-hidden rounded-xl border border-border bg-surface px-5 py-4"
                >
                  {renamingId === shelf.id ? (
                    <div className="relative flex flex-1 items-center gap-2">
                      <Input
                        className="h-11 flex-1"
                        aria-label={`New name for ${shelf.name}`}
                        value={renameValue}
                        autoFocus
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && renameValue.trim()) {
                            e.preventDefault();
                            rename.mutate({
                              id: shelf.id,
                              name: renameValue.trim(),
                            });
                          }
                          if (e.key === "Escape") setRenamingId(null);
                        }}
                      />
                      <Button
                        className="rounded-full"
                        onClick={() =>
                          rename.mutate({
                            id: shelf.id,
                            name: renameValue.trim(),
                          })
                        }
                      >
                        Save
                      </Button>
                      <Button
                        variant="ghost"
                        className="rounded-full"
                        onClick={() => setRenamingId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <>
                      {/* The bar: this row's share of the largest shelf, decorative
                        to assistive technology — the count beside it is the text
                        a screen reader gets (AC2). */}
                      <span
                        aria-hidden="true"
                        data-magnitude={String(share)}
                        style={{
                          width: `${Number((share * 100).toFixed(1))}%`,
                        }}
                        className="absolute inset-y-0 left-0 rounded-xl bg-primary/10"
                      />
                      {shelf.entry_count === 0 ? null : covers.length > 0 ? (
                        <CoverStack covers={covers} />
                      ) : (
                        // Entries exist but none of them carry a cover: the
                        // shared placeholder ("No cover", `CoverImage`'s own
                        // label), not a gap where the covers would have been
                        // (AC3). Left in the accessibility tree, unlike
                        // `CoverStack`'s own faces — it says something the row's
                        // count does not: this shelf has nothing to show.
                        <CoverImage
                          src={null}
                          alt=""
                          className="h-8 w-6 shrink-0 rounded-sm"
                        />
                      )}
                      <Link
                        to={`/?shelf=${encodeURIComponent(shelf.slug)}`}
                        className="focus-ring relative min-w-0 flex-1 rounded-md"
                      >
                        <p className="truncate font-semibold">{shelf.name}</p>
                        <p
                          className={
                            shelf.entry_count === 0
                              ? "text-sm text-muted-foreground"
                              : weightClass(shelf.entry_count, max)
                          }
                        >
                          {shelf.entry_count === 0
                            ? "Empty"
                            : `${shelf.entry_count} ${
                                shelf.entry_count === 1 ? "item" : "items"
                              }`}
                        </p>
                      </Link>
                      {/* Its own opaque backing: at a high share the magnitude
                          bar can extend the full row width, and the
                          destructive button's text otherwise renders against
                          that tint blended into the surface — enough to drop
                          below axe's contrast threshold on a near-full shelf. */}
                      <div className="relative flex shrink-0 gap-2 rounded-full bg-surface">
                        <Button
                          variant="outline"
                          className="rounded-full text-sm"
                          aria-label={`Rename ${shelf.name}`}
                          onClick={() => {
                            setRenamingId(shelf.id);
                            setRenameValue(shelf.name);
                          }}
                        >
                          Rename
                        </Button>
                        <Button
                          variant="outline"
                          className="rounded-full border-destructive/60 text-sm text-destructive hover:bg-destructive/10 hover:text-destructive"
                          aria-label={`Delete ${shelf.name}`}
                          onClick={() => setDeletingShelf(shelf)}
                        >
                          Delete
                        </Button>
                      </div>
                    </>
                  )}
                </li>
              );
            });
          })()}
        </ul>
      )}

      {/* Delete confirmation. Confirmation dialogs are limited to delete and
          explicit provider refresh (product spec section 7). */}
      <AlertDialog
        open={deletingShelf !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingShelf(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete &ldquo;{deletingShelf?.name}&rdquo;?
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
              onClick={() => deletingShelf && remove.mutate(deletingShelf.id)}
            >
              Delete shelf
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}
