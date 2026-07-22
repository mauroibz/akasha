import type { Shelf } from "./library";

export interface ShelfWithCount extends Shelf {
  entry_count: number;
}

async function jsonOrThrow<T>(
  response: Response,
  fallback: string,
): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(body?.error?.message ?? fallback);
  }
  return response.json() as Promise<T>;
}

export function getShelves() {
  return fetch("/api/shelves").then((r) =>
    jsonOrThrow<ShelfWithCount[]>(r, "Shelves could not be loaded"),
  );
}

export function createShelf(name: string) {
  return fetch("/api/shelves", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then((r) => jsonOrThrow<ShelfWithCount>(r, "Shelf could not be created"));
}

export function renameShelf(id: number, name: string) {
  return fetch(`/api/shelves/${id}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then((r) => jsonOrThrow<ShelfWithCount>(r, "Shelf could not be renamed"));
}

export function deleteShelf(id: number) {
  return fetch(`/api/shelves/${id}`, {
    method: "DELETE",
  }).then((r) => {
    if (!r.ok) throw new Error("Shelf could not be deleted");
  });
}
