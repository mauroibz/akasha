import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { createShelf, getShelves, type ShelfWithCount } from "@/api/shelves";
import { queryKeys } from "@/api/keys";
import type { ItemType } from "@/api/library";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SuggestedShelves } from "@/features/shelves/SuggestedShelves";
import { Input } from "@/components/ui/input";
import { Loading } from "@/components/ui/skeleton";
import { spelled } from "@/features/insights/prose";
import { countLabel, domainsFrom } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { OpeningCover } from "@/features/shelves/OpeningCover";
import { cn } from "@/lib/utils";

type ShelfSort = "size" | "recent" | "name";

const allDomains = "";

/** Every shelf's chosen count, honouring the domain filter (Sprint 074). */
function countFor(shelf: ShelfWithCount, domainFilter: string): number {
  if (!domainFilter) return shelf.entry_count;
  return shelf.members_by_type?.[domainFilter] ?? 0;
}

/** How many shelves before the page offers to search them by name. */
const searchFrom = 8;

/**
 * Shelves, drawn as shelves (Sprint 105, DEC-169). The owner on the card grid:
 * "too bland right now, it could be more opinionated." Each shelf is a row: its
 * name large, a line of character, and its covers standing face-out on a ledge,
 * the largest shelf drawn biggest. A cover opens on hover (`OpeningCover`).
 *
 * Deleting a shelf still only removes the tag; that is said on the shelf's own
 * page, where deleting happens.
 */
export function ShelvesPage() {
  const cache = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState("");
  const [domainFilter, setDomainFilter] = useState(allDomains);
  const [sort, setSort] = useState<ShelfSort>("size");
  const [query, setQuery] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);

  const itemTypes = useItemTypes();
  const domains = useMemo(() => domainsFrom(itemTypes.data), [itemTypes.data]);
  const shelves = useQuery({
    queryKey: queryKeys.shelves,
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
      setCreating(false);
      toast.success(`Shelf "${name}" created`);
      void cache.invalidateQueries({ queryKey: queryKeys.shelves });
    },
    onError: (e: Error) => setError(e.message),
  });

  // Only domains at least one shelf holds: a filter that always empties the room
  // is not a filter (Sprint 074).
  const domainsInUse = useMemo(() => {
    const ids = new Set<string>();
    for (const shelf of shelves.data ?? [])
      for (const id of Object.keys(shelf.members_by_type ?? {})) ids.add(id);
    return domains.filter((domain) => ids.has(domain.id));
  }, [shelves.data, domains]);

  const room = useMemo(() => {
    let rows = shelves.data ?? [];
    if (domainFilter)
      rows = rows.filter((shelf) => countFor(shelf, domainFilter) > 0);
    const typed = query.trim().toLowerCase();
    if (typed)
      rows = rows.filter((shelf) => shelf.name.toLowerCase().includes(typed));
    const sorted = [...rows];
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === "recent")
      sorted.sort((a, b) =>
        (b.updated_at ?? "").localeCompare(a.updated_at ?? ""),
      );
    else
      sorted.sort(
        (a, b) =>
          countFor(b, domainFilter) - countFor(a, domainFilter) ||
          a.name.localeCompare(b.name),
      );
    return sorted;
  }, [shelves.data, domainFilter, query, sort]);

  const all = shelves.data ?? [];
  const held = all.reduce((sum, shelf) => sum + shelf.entry_count, 0);
  const bestLoved = [...all]
    .filter((shelf) => shelf.entry_count >= 2 && shelf.mean_score != null)
    .sort((a, b) => (b.mean_score ?? 0) - (a.mean_score ?? 0))[0];
  const largest = Math.max(
    ...room.map((shelf) => countFor(shelf, domainFilter)),
    0,
  );

  return (
    <main className="mx-auto min-h-screen w-full max-w-[1280px] px-5 pb-24 pt-8 md:px-8 md:pt-12">
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-6">
        <div>
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="font-display text-6xl font-normal leading-[0.95] tracking-[-0.02em] focus:outline-none md:text-8xl"
          >
            Shelves
          </h1>
          {all.length > 0 && (
            <p className="mt-4 max-w-[40ch] font-display text-xl leading-snug text-foreground/85 md:text-2xl">
              {capital(spelled(all.length))}{" "}
              {all.length === 1 ? "shelf" : "shelves"},{" "}
              <span className="text-primary">
                {held} {held === 1 ? "thing" : "things"}
              </span>{" "}
              on them.
              {bestLoved && (
                <>
                  {" "}
                  Your best-loved is <i>{bestLoved.name}</i>.
                </>
              )}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {all.length > 1 && (
            <div role="group" aria-label="Sort shelves" className="flex gap-4">
              {(
                [
                  ["size", "Largest"],
                  ["recent", "Recent"],
                  ["name", "A–Z"],
                ] as const
              ).map(([value, label]) => (
                <TextToggle
                  key={value}
                  pressed={sort === value}
                  onClick={() => setSort(value)}
                >
                  {label}
                </TextToggle>
              ))}
            </div>
          )}
          <Button
            variant="outline"
            aria-expanded={creating}
            onClick={() => setCreating((open) => !open)}
            className="rounded-full border-[1.5px] border-foreground px-5 font-semibold"
          >
            + New shelf
          </Button>
        </div>
      </div>

      {creating && (
        <form
          className="mt-6 flex max-w-lg flex-wrap gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (newName.trim()) create.mutate(newName.trim());
          }}
        >
          <Input
            autoFocus
            className="h-11 min-w-[14rem] flex-1"
            aria-label="New shelf name"
            placeholder="A name for it"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Button
            type="submit"
            className="rounded-full px-5"
            disabled={!newName.trim() || create.isPending}
          >
            Create shelf
          </Button>
        </form>
      )}
      {error && (
        <p role="alert" className="mt-4 text-destructive">
          {error}
        </p>
      )}

      {(domainsInUse.length > 1 || all.length > searchFrom) && (
        <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-border">
          {domainsInUse.length > 1 && (
            <div
              role="radiogroup"
              aria-label="Choose a domain"
              className="-mb-px flex gap-5 overflow-x-auto"
            >
              {[
                { id: allDomains, label: "All", plural_label: "All" },
                ...domainsInUse,
              ].map((domain) => (
                <button
                  key={domain.id}
                  type="button"
                  role="radio"
                  aria-checked={domain.id === domainFilter}
                  onClick={() => setDomainFilter(domain.id)}
                  className={cn(
                    "min-h-11 shrink-0 border-b-2 text-sm font-medium focus-ring",
                    domain.id === domainFilter
                      ? "border-primary text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {domain.plural_label ?? domain.label}
                </button>
              ))}
            </div>
          )}
          {all.length > searchFrom && (
            <label className="ml-auto min-w-48">
              <span className="sr-only">Search shelves by name</span>
              <Input
                className="h-10 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
                type="search"
                placeholder="Find a shelf"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
          )}
        </div>
      )}

      <SuggestedShelves />

      {shelves.isPending && (
        <Loading label="Loading shelves…" shape="grid" className="mt-10" />
      )}
      {shelves.isError && (
        <p role="alert" className="mt-10 text-destructive">
          Shelves could not be loaded
        </p>
      )}
      {shelves.data && shelves.data.length === 0 && (
        <EmptyState title="No shelves yet" className="mt-10">
          A shelf is any collection you want to keep together: favourites, a
          reading group, the records you would save from a fire.
        </EmptyState>
      )}
      {shelves.data && shelves.data.length > 0 && room.length === 0 && (
        <p className="mt-10 text-muted-foreground">
          No shelf matches this filter.
        </p>
      )}

      <ol className="mt-6">
        {room.map((shelf) => (
          <ShelfRow
            key={shelf.id}
            shelf={shelf}
            types={itemTypes.data}
            lead={countFor(shelf, domainFilter) === largest && largest > 0}
          />
        ))}
      </ol>
    </main>
  );
}

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

function TextToggle({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        "min-h-11 text-sm font-medium underline-offset-[7px] focus-ring",
        pressed
          ? "text-foreground underline decoration-primary decoration-2"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

/** What a shelf holds, by its domains' own names. */
function kindOf(shelf: ShelfWithCount, types: ItemType[] | undefined): string {
  const ids = Object.keys(shelf.members_by_type ?? {});
  if (shelf.entry_count === 0) return "Empty";
  return ids
    .map((id) => types?.find((type) => type.id === id)?.plural_label ?? id)
    .join(" · ");
}

/** The shelf's line of character: how many, how many finished, how you rate them. */
function lineOf(shelf: ShelfWithCount, types: ItemType[] | undefined): string {
  if (shelf.entry_count === 0)
    return "Nothing here yet. Add to it from anything's own page.";
  const ids = Object.keys(shelf.members_by_type ?? {});
  const parts = [
    ids.length === 1
      ? countLabel(shelf.entry_count, ids[0], types)
      : `${shelf.entry_count} things`,
  ];
  if (shelf.finished_count) parts.push(`${shelf.finished_count} finished`);
  if (shelf.mean_score != null)
    parts.push(`you rate them ${shelf.mean_score.toFixed(1)}`);
  return parts.join(" · ");
}

/**
 * Which covers a ledge stands up at this width: as many as fit, never a ledge
 * that scrolls (a scrolling ledge clips the cover that opens on hover, and its 3D
 * layers widened the page). Two on a phone; up to five large or six on a wide
 * screen. The ledge ends with "See all N" either way.
 */
function fits(index: number, lead: boolean): string | false {
  if (index < 2) return false;
  if (index < (lead ? 3 : 4)) return "hidden sm:block md:hidden lg:block";
  if (index < (lead ? 5 : 6)) return "hidden xl:block";
  return "hidden";
}

function ShelfRow({
  shelf,
  types,
  lead,
}: {
  shelf: ShelfWithCount;
  types: ItemType[] | undefined;
  lead: boolean;
}) {
  const preview = shelf.preview ?? [];
  const href = `/shelves/${encodeURIComponent(shelf.slug)}`;
  return (
    <li
      data-shelf-row={shelf.slug}
      className="grid items-end gap-4 pt-10 md:grid-cols-[17rem_minmax(0,1fr)] md:gap-12 md:pt-12"
    >
      <div className="md:pb-6">
        <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
          {kindOf(shelf, types)}
        </div>
        <h2
          className={cn(
            "mt-1.5 font-display font-normal leading-none tracking-[-0.01em]",
            lead ? "text-5xl md:text-6xl" : "text-4xl md:text-5xl",
          )}
        >
          <Link to={href} className="hover:text-primary focus-ring">
            {shelf.name}
          </Link>
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          {lineOf(shelf, types)}
        </p>
      </div>
      <div className="min-w-0">
        <div
          className={cn(
            "flex items-end gap-3 px-3 pt-4 md:gap-4 md:px-5",
            lead ? "min-h-[16rem]" : "min-h-[12.5rem]",
          )}
        >
          {preview.length === 0 && (
            <span
              aria-hidden="true"
              className="h-44 w-[7.25rem] shrink-0 rounded-[2px_6px_6px_2px] border-[1.5px] border-dashed border-border"
            />
          )}
          {preview.map((member, index) => (
            <OpeningCover
              key={member.entry_id}
              href={`/books/${member.entry_id}`}
              title={member.title}
              year={member.year}
              score={member.score}
              coverUrl={member.cover_url}
              seed={member.entry_id}
              tilt={index % 4 === 3}
              className={cn(
                lead
                  ? "h-44 w-28 sm:h-56 sm:w-[9.5rem]"
                  : "h-40 w-[6.5rem] sm:h-44 sm:w-[7.25rem]",
                index % 3 === 1 && (lead ? "h-40 sm:h-52" : "h-36 sm:h-40"),
                fits(index, lead),
              )}
            />
          ))}
          {shelf.entry_count > 2 && (
            <Link
              to={href}
              className="ml-2 shrink-0 self-center whitespace-nowrap text-sm font-medium text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground focus-ring"
            >
              <span className="sm:hidden">All {shelf.entry_count}</span>
              <span className="hidden sm:inline">
                See all {shelf.entry_count}
              </span>
              <span className="sr-only"> on {shelf.name}</span>
            </Link>
          )}
        </div>
        <div
          aria-hidden="true"
          className="h-3.5 rounded-[3px] bg-[#B8915F] shadow-[inset_0_-4px_0_#8A6A45,0_14px_18px_-12px_rgba(28,25,23,0.55)] dark:bg-[#6B5238] dark:shadow-[inset_0_-4px_0_#4A3826,0_14px_18px_-12px_rgba(0,0,0,0.8)]"
        />
      </div>
    </li>
  );
}
