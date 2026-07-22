import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

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
  const [toast, setToast] = useState("");
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
    onSuccess: () => {
      setError("");
      setNewName("");
      void cache.invalidateQueries({ queryKey: ["shelves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const rename = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      renameShelf(id, name),
    onSuccess: () => {
      setRenamingId(null);
      setError("");
      void cache.invalidateQueries({ queryKey: ["shelves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteShelf(id),
    onSuccess: () => {
      setDeletingShelf(null);
      setToast("Shelf deleted. Your books are retained.");
      void cache.invalidateQueries({ queryKey: ["shelves"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-5 py-8">
      <button className="focus-ring" onClick={() => navigate("/")}>
        ← Library
      </button>
      <h1
        ref={headingRef}
        tabIndex={-1}
        className="mt-6 text-4xl font-semibold focus:outline-none"
      >
        Shelves
      </h1>
      <p className="mt-2 text-zinc-400">
        Organize your library with custom shelves. Deleting a shelf removes the
        tag from your books but never deletes the books themselves.
      </p>

      {/* Create shelf */}
      <section className="mt-6 flex gap-2">
        <input
          className="field flex-1"
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
        <button
          className="min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring disabled:opacity-50"
          disabled={!newName.trim() || create.isPending}
          onClick={() => create.mutate(newName.trim())}
        >
          Create shelf
        </button>
      </section>

      {error && (
        <p role="alert" className="mt-4 text-red-300">
          {error}
        </p>
      )}
      {toast && (
        <p role="status" className="mt-4 text-fuchsia-300">
          {toast}
        </p>
      )}

      {/* Shelf list */}
      {shelves.isPending && (
        <p role="status" className="mt-8 text-zinc-400">
          Loading shelves…
        </p>
      )}
      {shelves.isError && (
        <p role="alert" className="mt-8 text-red-300">
          Shelves could not be loaded
        </p>
      )}
      {shelves.data && shelves.data.length === 0 && (
        <p className="mt-8 text-zinc-400">No shelves yet. Create one above.</p>
      )}
      {shelves.data && shelves.data.length > 0 && (
        <ul className="mt-6 space-y-3">
          {shelves.data.map((shelf) => (
            <li
              key={shelf.id}
              className="flex items-center justify-between rounded-xl border border-zinc-800 px-5 py-4"
            >
              {renamingId === shelf.id ? (
                <div className="flex flex-1 items-center gap-2">
                  <input
                    className="field flex-1"
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
                  <button
                    className="min-h-11 rounded-full bg-fuchsia-500 px-4 font-semibold text-zinc-950 focus-ring"
                    onClick={() =>
                      rename.mutate({ id: shelf.id, name: renameValue.trim() })
                    }
                  >
                    Save
                  </button>
                  <button
                    className="focus-ring rounded-full px-3 text-zinc-400"
                    onClick={() => setRenamingId(null)}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <>
                  <div>
                    <p className="font-semibold">{shelf.name}</p>
                    <p className="text-sm text-zinc-500">
                      {shelf.entry_count}{" "}
                      {shelf.entry_count === 1 ? "book" : "books"}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="min-h-11 rounded-full border border-zinc-700 px-4 text-sm focus-ring"
                      aria-label={`Rename ${shelf.name}`}
                      onClick={() => {
                        setRenamingId(shelf.id);
                        setRenameValue(shelf.name);
                      }}
                    >
                      Rename
                    </button>
                    <button
                      className="min-h-11 rounded-full border border-red-800 px-4 text-sm text-red-300 focus-ring"
                      aria-label={`Delete ${shelf.name}`}
                      onClick={() => setDeletingShelf(shelf)}
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Delete confirmation dialog */}
      {deletingShelf && (
        <div
          role="dialog"
          aria-label="Confirm shelf deletion"
          aria-modal="true"
          className="dialog"
        >
          <h2>Delete &ldquo;{deletingShelf.name}&rdquo;?</h2>
          <p>
            This shelf will be removed from all your books. The books themselves
            are retained and remain in your library.
          </p>
          <button
            autoFocus
            className="min-h-11 rounded-full bg-red-600 px-5 font-semibold text-zinc-950 focus-ring"
            onClick={() => remove.mutate(deletingShelf.id)}
          >
            Delete shelf
          </button>
          <button
            className="focus-ring rounded-full px-4"
            onClick={() => setDeletingShelf(null)}
          >
            Cancel
          </button>
        </div>
      )}
    </main>
  );
}
