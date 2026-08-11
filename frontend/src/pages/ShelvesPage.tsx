import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

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
import { cn } from "@/lib/utils";
import {
  createShelf,
  deleteShelf,
  getShelves,
  renameShelf,
  type ShelfWithCount,
} from "@/api/shelves";

export function ShelvesPage() {
  const navigate = useNavigate();
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
        description: "Your books are retained.",
      });
      void cache.invalidateQueries({ queryKey: ["shelves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-5 py-8">
      <Button variant="ghost" className="px-0" onClick={() => navigate("/")}>
        ← Library
      </Button>
      <h1
        ref={headingRef}
        tabIndex={-1}
        className="mt-6 text-4xl font-semibold focus:outline-none"
      >
        Shelves
      </h1>
      <p className="mt-2 text-muted-foreground">
        Organize your library with custom shelves. Deleting a shelf removes the
        tag from your books but never deletes the books themselves.
      </p>

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
          {shelves.data.map((shelf) => (
            <li
              key={shelf.id}
              className="flex items-center justify-between rounded-xl border border-border px-5 py-4"
            >
              {renamingId === shelf.id ? (
                <div className="flex flex-1 items-center gap-2">
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
                      rename.mutate({ id: shelf.id, name: renameValue.trim() })
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
                  <div>
                    <p className="font-semibold">{shelf.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {shelf.entry_count}{" "}
                      {shelf.entry_count === 1 ? "book" : "books"}
                    </p>
                  </div>
                  <div className="flex gap-2">
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
          ))}
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
              This shelf will be removed from all your books. The books
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
