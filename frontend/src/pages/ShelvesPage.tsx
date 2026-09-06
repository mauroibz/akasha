import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/PageHeader";
import { DomainStrip } from "@/components/DomainStrip";
import { SegmentedControl } from "@/components/SegmentedControl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShelfCard } from "@/features/shelves/ShelfCard";
import { domainsFrom } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { createShelf, getShelves, type ShelfWithCount } from "@/api/shelves";

type ShelfSort = "size" | "name" | "recent";

const allDomains = "";

/** Every shelf's chosen count, honouring the domain filter (deliverable 3). */
function countFor(shelf: ShelfWithCount, domainFilter: string): number {
  if (!domainFilter) return shelf.entry_count;
  return shelf.members_by_type?.[domainFilter] ?? 0;
}

export function ShelvesPage() {
  const cache = useQueryClient();
  const [newName, setNewName] = useState("");
  const [error, setError] = useState("");
  const [domainFilter, setDomainFilter] = useState(allDomains);
  const [sort, setSort] = useState<ShelfSort>("size");
  const [query, setQuery] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);

  const itemTypes = useItemTypes();
  const domains = useMemo(() => domainsFrom(itemTypes.data), [itemTypes.data]);

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

  // Only domains at least one shelf actually holds -- offering "Album" on a
  // library with no album shelves would be a filter that always empties the
  // board (deliverable 3).
  const domainsInUse = useMemo(() => {
    const ids = new Set<string>();
    for (const shelf of shelves.data ?? [])
      for (const id of Object.keys(shelf.members_by_type ?? {})) ids.add(id);
    return domains.filter((domain) => ids.has(domain.id));
  }, [shelves.data, domains]);

  const board = useMemo(() => {
    let rows = shelves.data ?? [];
    if (domainFilter)
      rows = rows.filter((shelf) => countFor(shelf, domainFilter) > 0);
    const typed = query.trim().toLowerCase();
    if (typed)
      rows = rows.filter((shelf) => shelf.name.toLowerCase().includes(typed));
    const sorted = [...rows];
    if (sort === "name") {
      sorted.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sort === "recent") {
      sorted.sort((a, b) =>
        (b.updated_at ?? "").localeCompare(a.updated_at ?? ""),
      );
    } else {
      sorted.sort(
        (a, b) =>
          countFor(b, domainFilter) - countFor(a, domainFilter) ||
          a.name.localeCompare(b.name),
      );
    }
    return sorted;
  }, [shelves.data, domainFilter, query, sort]);

  const max = Math.max(
    ...board.map((shelf) => countFor(shelf, domainFilter)),
    1,
  );

  return (
    <main className="mx-auto min-h-screen max-w-[1600px] px-5 py-8">
      <PageHeader
        back
        headingRef={headingRef}
        title="Shelves"
        lede="Organize your library with custom shelves. Deleting a shelf removes the tag from what is on it, but never deletes anything itself."
      />

      <section className="mt-6 flex flex-wrap items-center gap-3">
        <Input
          className="h-11 min-w-[200px] flex-1"
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
          className="h-11 rounded-full px-5"
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

      {shelves.data && shelves.data.length > 0 && (
        <section className="mt-6 flex flex-wrap items-center gap-3">
          {domainsInUse.length > 1 && (
            <DomainStrip
              domains={[{ id: allDomains, label: "All" }, ...domainsInUse]}
              value={domainFilter}
              onChange={setDomainFilter}
            />
          )}
          <SegmentedControl
            ariaLabel="Sort shelves"
            value={sort}
            onChange={setSort}
            options={[
              { value: "size", label: "Largest" },
              { value: "recent", label: "Recently added" },
              { value: "name", label: "Name" },
            ]}
          />
          <label className="relative min-w-40 flex-1">
            <span className="sr-only">Search shelves by name</span>
            <Input
              className="h-11"
              type="search"
              placeholder="Search shelves"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </section>
      )}

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
      {shelves.data && shelves.data.length > 0 && board.length === 0 && (
        <p className="mt-8 text-muted-foreground">
          No shelf matches this filter.
        </p>
      )}
      {board.length > 0 && (
        <ul className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {board.map((shelf) => (
            <li key={shelf.id}>
              <ShelfCard
                shelf={shelf}
                max={max}
                domains={domains}
                domainFilter={domainFilter || undefined}
              />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
