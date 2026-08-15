import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import type { FieldSpec } from "@/api/library";
import {
  deleteEntry,
  getEntry,
  getItemTypes,
  patchEntry,
  patchItem,
  refreshItem,
  chooseCover,
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
import { Attachments } from "@/features/detail/Attachments";
import { CoverDialog } from "@/features/detail/CoverDialog";
import { MetadataDialog } from "@/features/detail/MetadataDialog";
import { OpinionDialog } from "@/features/detail/OpinionDialog";
import { optionalInt, toMetadataPatch } from "@/features/detail/schemas";
import {
  entryPanelLabel,
  formatLabels,
  hasEntryField,
  statusLabelFor,
} from "@/features/library/labels";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";

/** One term/definition pair, addressable by name instead of by CSS adjacency. */
/**
 * A metadata value rendered from what its domain says it is, rather than from a
 * branch on the item's type: an album has no page count and a book has no label,
 * and neither screen should know the other's vocabulary (DEC-052 seam 3).
 */
function formatFact(value: unknown, field: FieldSpec): string {
  if (field.multiplicity === "many")
    return Array.isArray(value) && value.length ? value.join(", ") : "—";
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

/** A duration in milliseconds as a listener reads it: 9:22, or 1:02:11.
 *
 * Truncated rather than rounded, which is what every player does: a 3:32.5 track
 * reads 3:32 on the sleeve and on the display, and rounding it up to 3:33 would
 * disagree with both.
 */
function duration(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0)
    return "";
  const total = Math.floor(value / 1000);
  const parts = [Math.floor(total / 60) % 60, total % 60];
  if (total >= 3600) parts.unshift(Math.floor(total / 3600));
  return parts
    .map((part, index) =>
      index ? String(part).padStart(2, "0") : String(part),
    )
    .join(":");
}

/**
 * An ordered list of structured rows — a tracklist — rendered from the columns its
 * domain declares rather than from anything this screen knows about music.
 *
 * A tracklist is metadata on the album, not a set of child entities: it is read,
 * never opened, and nothing hangs off a track (Sprint 025 non-scope, still true).
 */
function RowsField({ field, value }: { field: FieldSpec; value: unknown }) {
  const rows = Array.isArray(value) ? value : [];
  // Absent and empty are the same thing, so a book gains no empty tracklist and
  // neither does a release with no recordings.
  if (!rows.length || !field.columns?.length) return null;
  const columns = field.columns;
  return (
    <section
      className="mt-6 rounded-xl border border-border p-5"
      aria-label={field.label}
    >
      <h2 className="text-sm font-semibold uppercase tracking-wider text-primary">
        {field.label}
      </h2>
      <ol className="mt-4 grid gap-1" data-rows={field.name}>
        {rows.map((row, index) => {
          const cells = (row ?? {}) as Record<string, unknown>;
          return (
            <li
              key={index}
              className="flex items-baseline gap-3 border-b border-border/40 py-1 last:border-0"
            >
              {columns.map((column) => (
                <span
                  key={column.name}
                  data-column={column.name}
                  className={
                    column.name === "title"
                      ? "min-w-0 flex-1 truncate text-foreground"
                      : "shrink-0 tabular-nums text-sm text-muted-foreground"
                  }
                >
                  {column.type === "duration"
                    ? duration(cells[column.name])
                    : String(cells[column.name] ?? "")}
                </span>
              ))}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

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
    "opinion" | "metadata" | "refresh" | "delete" | "cover" | null
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
  // The fields belong to the item's domain and change with a deployment, not with
  // an edit, so they are fetched once and shared by the facts panel and the dialog.
  const itemTypes = useQuery({
    queryKey: ["item-types"],
    queryFn: getItemTypes,
    retry: false,
    staleTime: Infinity,
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

  if (detail.isPending) return <p role="status">Loading detail…</p>;
  if (!detail.data) return <p role="alert">Detail could not be loaded</p>;
  const entry = detail.data;
  const item = entry.item;
  const fields =
    itemTypes.data?.find((type) => type.id === item.type)?.fields ?? [];
  const inlineFields = fields.filter(
    (field) =>
      field.type !== "long_text" &&
      field.type !== "rows" &&
      field.name !== "creators",
  );
  const blockFields = fields.filter((field) => field.type === "long_text");
  // An ordered list of structured rows is neither a fact nor a paragraph, so it
  // gets its own region rather than being joined into one line (a tracklist).
  const rowFields = fields.filter((field) => field.type === "rows");
  const editableFields = fields.filter((field) => field.type !== "rows");
  const has = (field: "date_started" | "date_finished" | "reread_count") =>
    hasEntryField(item.type, itemTypes.data, field);

  async function handleDelete() {
    setDeleteError("");
    try {
      await deleteEntry(entry.id);
      void cache.invalidateQueries({ queryKey: ["library"] });
      toast.success("Removed from your library");
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
          <Button
            variant="secondary"
            className="mt-3 w-full"
            onClick={() => setDialog("cover")}
          >
            Choose a cover
          </Button>
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
            {item.creator ?? "Unknown creator"}
          </p>
          <p className="text-sm text-muted-foreground">
            Edition year: {item.year ?? "unknown"}
            {typeof item.metadata.original_year === "number" &&
            item.metadata.original_year !== item.year
              ? ` · Originally published: ${item.metadata.original_year}`
              : ""}
          </p>

          {/* The personal region. Its heading is the domain's: an album's entry
              records possession rather than reading, so "Your reading data" over a
              record was seam 5a showing through (DEC-057). */}
          <section
            className="mt-6 rounded-xl border border-border p-5"
            aria-label={entryPanelLabel(item.type, itemTypes.data)}
          >
            <h2 className="text-sm font-semibold uppercase tracking-wider text-primary">
              {entryPanelLabel(item.type, itemTypes.data)}
            </h2>
            <dl className="mt-4 grid grid-cols-2 gap-4">
              <Fact name="status" label="Status">
                {statusLabelFor(item.type, itemTypes.data, entry.status)}
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
              <Fact name="formats" label="Format">
                {(entry.formats ?? [])
                  .map(
                    (format) => formatLabels(itemTypes.data)[format] ?? format,
                  )
                  .join(", ") || "—"}
              </Fact>
              {has("date_started") && (
                <Fact name="started" label="Started">
                  {entry.date_started ?? "—"}
                </Fact>
              )}
              {has("date_finished") && (
                <Fact name="finished" label="Finished">
                  {entry.date_finished ?? "—"}
                </Fact>
              )}
              {has("reread_count") && (
                <Fact name="rereads" label="Rereads">
                  {entry.reread_count}
                </Fact>
              )}
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
              {inlineFields.map((field) => (
                <Fact key={field.name} name={field.name} label={field.label}>
                  {formatFact(item.metadata[field.name], field)}
                </Fact>
              ))}
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
            {blockFields.map((field) => {
              const value = formatFact(item.metadata[field.name], field);
              return value === "—" ? null : (
                <div key={field.name} className="mt-4">
                  <p className="text-xs text-muted-foreground">{field.label}</p>
                  <p className="mt-1 whitespace-pre-wrap text-foreground">
                    {value}
                  </p>
                </div>
              );
            })}
            <div className="mt-5">
              <Attachments itemId={item.id} />
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button
                variant="outline"
                className="rounded-full px-5"
                onClick={() => setDialog("metadata")}
              >
                Edit metadata
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

          {rowFields.map((field) => (
            <RowsField
              key={field.name}
              field={field}
              value={item.metadata[field.name]}
            />
          ))}
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
                shelf_ids: values.shelf_ids,
                formats: values.formats,
                // Sent only by a domain that has them. The server refuses a reread
                // count on a record with a 422, and it is right to (DEC-057).
                ...(has("date_started")
                  ? { date_started: values.date_started || null }
                  : {}),
                ...(has("date_finished")
                  ? { date_finished: values.date_finished || null }
                  : {}),
                ...(has("reread_count")
                  ? { reread_count: Number(values.reread_count || 0) }
                  : {}),
              }),
            )
            .then(() => undefined)
        }
        onCreateShelf={handleCreateShelf}
      />

      <CoverDialog
        open={dialog === "cover"}
        onOpenChange={(open) => setDialog(open ? "cover" : null)}
        item={item}
        onChoose={(coverUrl) =>
          update
            .mutateAsync(() => chooseCover(item.id, coverUrl))
            .then(() => undefined)
        }
      />

      <MetadataDialog
        open={dialog === "metadata"}
        onOpenChange={(open) => setDialog(open ? "metadata" : null)}
        item={item}
        // A `rows` field is read here and not edited: correcting a tracklist by
        // hand is a table editor, and the sprint that added the field type
        // deliberately did not also build one. `Refresh from provider` is the way
        // a wrong tracklist gets fixed today.
        fields={editableFields}
        onSave={(values) =>
          update
            .mutateAsync(() =>
              patchItem(item.id, {
                title: values.title.trim(),
                subtitle: values.subtitle || null,
                year: optionalInt(values.year),
                creator_sort_override:
                  values.creator_sort_override.trim() || null,
                metadata: toMetadataPatch(values, fields),
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
            <AlertDialogTitle>Remove this from your library?</AlertDialogTitle>
            <AlertDialogDescription>
              Your score, status, notes, and shelf assignments will be deleted.
              The metadata and cover remain cached so re-adding is instant.
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
