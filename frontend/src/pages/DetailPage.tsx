import {
  Bookmark,
  CalendarCheck,
  CalendarPlus,
  CircleDot,
  Gauge,
  Repeat,
  Shapes,
  Star,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import type { FieldSpec } from "@/api/library";
import {
  deleteEntry,
  getEntry,
  getItemTypes,
  patchEntry,
  patchItem,
  refreshItem,
  fetchProviderCover,
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
import { BackToLibrary } from "@/components/BackToLibrary";
import { CoverImage } from "@/components/CoverImage";
import { Panel } from "@/components/Panel";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Label } from "@/components/ui/label";
import { Attachments } from "@/features/detail/Attachments";
import { CoverDialog } from "@/features/detail/CoverDialog";
import { MetadataDialog } from "@/features/detail/MetadataDialog";
import { OpinionDialog } from "@/features/detail/OpinionDialog";
import { ShelfPicker } from "@/features/shelves/ShelfPicker";
import { optionalInt, toMetadataPatch } from "@/features/detail/schemas";
import {
  choosesCovers,
  entryFieldLabel,
  entryPanelLabel,
  formatLabels,
  hasEntryField,
  progressFor,
  statusLabelFor,
} from "@/features/library/labels";
import type { EntryFieldName } from "@/features/library/labels";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";
import { queryKeys } from "@/api/keys";
import {
  cachedEntry,
  coverTransitionName,
} from "@/features/library/cachedEntry";
import { FilePicker } from "@/components/ui/file-picker";
import { Loading } from "@/components/ui/skeleton";

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
  const headingId = `rows-field-${field.name}-heading`;
  return (
    <Panel
      className="mt-6"
      aria-labelledby={headingId}
      heading={field.label}
      headingId={headingId}
    >
      <ol className="grid gap-1" data-rows={field.name}>
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
    </Panel>
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

/**
 * One of your values on the detail page, as a property row (Sprint 092, DEC-165):
 * a muted label with its icon, the value beside it, a soft fill on hover. A row
 * whose value the opinion dialog edits opens that dialog on click, and carries a
 * small "Change" button for the keyboard; nothing new becomes editable. Keeps the
 * `data-fact`/`dt`/`dd` shape every test and spec reads.
 */
function PropertyRow({
  name,
  label,
  icon,
  onEdit,
  children,
}: {
  name: string;
  label: string;
  icon: React.ReactNode;
  onEdit?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      data-fact={name}
      onClick={onEdit}
      className={cn(
        "group -mx-2 grid grid-cols-[9.5rem_1fr] items-center gap-3 rounded-md px-2 py-1.5 transition-colors sm:grid-cols-[11rem_1fr]",
        onEdit && "cursor-pointer hover:bg-muted/70",
      )}
    >
      <dt className="flex items-center gap-2 text-sm text-muted-foreground [&_svg]:h-4 [&_svg]:w-4 [&_svg]:shrink-0">
        {icon}
        {label}
      </dt>
      <dd className="flex min-w-0 items-center justify-between gap-2">
        {children}
        {onEdit ? (
          // Named by aria-label and worded by CSS, so the value's own text is all
          // a reader of `dd` finds, and the button stays inside the `dd` a
          // definition list allows (Sprint 092).
          <button
            type="button"
            aria-label={`Change ${label.toLowerCase()}`}
            onClick={(event) => {
              event.stopPropagation();
              onEdit();
            }}
            className="ml-auto shrink-0 rounded px-1.5 text-xs text-muted-foreground opacity-0 transition-opacity after:content-['Change'] focus-ring focus-visible:opacity-100 group-hover:opacity-100"
          />
        ) : null}
      </dd>
    </div>
  );
}

export function DetailPage() {
  const entryId = Number(useParams().entryId);
  const cache = useQueryClient();
  const navigate = useNavigate();
  // Where this detail page was opened from, when it says: a triage row sends
  // `from: "triage"` so its back control returns to the inbox the reader was
  // working through, instead of the library. Absent (a deep link, the library)
  // means the library — the only place left to go back to.
  const from = (useLocation().state as { from?: string } | null)?.from;
  const backTo = from === "triage" ? "/inbox" : "/";
  const backLabel = from === "triage" ? "Inbox" : "Library";
  const [dialog, setDialog] = useState<
    "opinion" | "metadata" | "refresh" | "delete" | "cover" | null
  >(null);
  const [error, setError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const detail = useQuery({
    queryKey: queryKeys.entry(entryId),
    queryFn: () => getEntry(entryId),
    retry: false,
    // Start from the list it was opened from, so the page and its cover are there
    // in the first frame and the cover can grow out of the library card (Sprint
    // 092); the entry's own read replaces it a moment later.
    placeholderData: () => cachedEntry(cache, entryId),
  });
  const shelves = useQuery({
    queryKey: queryKeys.shelves,
    queryFn: getShelves,
    retry: false,
  });
  // The fields belong to the item's domain and change with a deployment, not with
  // an edit, so they are fetched once and shared by the facts panel and the dialog.
  const itemTypes = useQuery({
    queryKey: queryKeys.itemTypes,
    queryFn: getItemTypes,
    retry: false,
    staleTime: Infinity,
  });
  const update = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      setError("");
      void cache.invalidateQueries({ queryKey: queryKeys.entry(entryId) });
      void cache.invalidateQueries({ queryKey: queryKeys.library.all });
    },
    onError: (value: Error) => setError(value.message),
  });

  useEffect(() => {
    if (detail.data) headingRef.current?.focus();
  }, [detail.data]);

  // Focus trapping, initial focus, and Escape-to-close were all hand-rolled
  // here. Radix Dialog owns them now, so the hand-rolled versions are gone
  // rather than left to fight it.

  if (detail.isPending)
    return (
      <main className="mx-auto max-w-5xl px-4 py-10">
        <Loading label="Loading detail…" shape="detail" />
      </main>
    );
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
  const has = (field: EntryFieldName) =>
    hasEntryField(item.type, itemTypes.data, field);
  // The domain's own word for the field, not a book's (technical spec 6.6).
  const nameOf = (field: EntryFieldName) =>
    entryFieldLabel(item.type, itemTypes.data, field);
  const progress = progressFor(item.type, itemTypes.data);
  // The total is the item's own metadata and is often absent — an airing series has
  // none — so the reading falls back to the bare count rather than "20 / —".
  const progressTotal =
    progress?.total_field != null
      ? item.metadata[progress.total_field]
      : undefined;

  async function handleDelete() {
    setDeleteError("");
    try {
      await deleteEntry(entry.id);
      void cache.invalidateQueries({ queryKey: queryKeys.library.all });
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

  /**
   * Create a shelf and hand it back, so the caller can put this entry on it
   * without a second trip through the UI.
   *
   * The error is re-thrown as well as reported: the picker has to know the shelf
   * does not exist, or it would go on to assign an id it never received.
   */
  async function handleCreateShelf(name: string) {
    try {
      const created = await createShelf(name);
      void cache.invalidateQueries({ queryKey: queryKeys.shelves });
      toast.success(`Shelf "${name}" created`);
      return created;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Shelf could not be created");
      throw e;
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <BackToLibrary to={backTo} label={backLabel} />
      <div className="mt-8 grid gap-8 md:grid-cols-[240px_1fr]">
        <aside>
          <div style={{ viewTransitionName: coverTransitionName(entry.id) }}>
            <CoverImage
              src={item.cover_url}
              alt={`Cover of ${item.title}`}
              className="aspect-[2/3] w-full rounded-xl"
            />
          </div>
          {/* Asked of the domain, not branched on the type: the chooser is Open
              Library's work-editions path, and an album has no work and no
              editions, so the control could only ever say no (DEC-067 row 7). */}
          {choosesCovers(item.type, itemTypes.data) && (
            <Button
              variant="secondary"
              className="mt-3 w-full"
              onClick={() => setDialog("cover")}
            >
              Choose a cover
            </Button>
          )}
          {/* The domain with no cover chooser has one provider's cover, not a list
              of editions to pick from — so the action a missing one needs is
              "try that provider again", not "overwrite everything" (which is what
              `Refresh from provider` does, behind a confirmation, for a much
              larger reason). Offered only where it can do something: an item
              with no provider source at all has nowhere to fetch a cover from. */}
          {!item.cover_url &&
            !choosesCovers(item.type, itemTypes.data) &&
            item.sources.some((source) => source.is_primary) && (
              <Button
                variant="secondary"
                className="mt-3 w-full"
                onClick={() => update.mutate(() => fetchProviderCover(item.id))}
              >
                Fetch cover
              </Button>
            )}
          <div className="mt-3 block text-sm">
            <Label htmlFor="replace-cover">Replace cover</Label>
            <FilePicker
              id="replace-cover"
              className="mt-1"
              buttonLabel="Upload an image"
              showChosen={false}
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
            className="font-display text-5xl font-medium leading-[1.05] tracking-tight focus:outline-none sm:text-6xl"
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
          <Panel
            className="mt-6"
            aria-labelledby="entry-panel-heading"
            heading={entryPanelLabel(item.type, itemTypes.data)}
            headingId="entry-panel-heading"
          >
            <dl className="space-y-0.5">
              <PropertyRow
                name="status"
                label="Status"
                icon={<CircleDot aria-hidden="true" />}
                onEdit={() => setDialog("opinion")}
              >
                <span className="inline-flex rounded-full bg-primary/15 px-2.5 py-0.5 text-sm font-medium text-primary">
                  {statusLabelFor(item.type, itemTypes.data, entry.status)}
                </span>
              </PropertyRow>
              <PropertyRow
                name="score"
                label="Score"
                icon={<Star aria-hidden="true" />}
                onEdit={() => setDialog("opinion")}
              >
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
              </PropertyRow>
              <PropertyRow
                name="formats"
                label="Format"
                icon={<Shapes aria-hidden="true" />}
                onEdit={() => setDialog("opinion")}
              >
                {(entry.formats ?? [])
                  .map(
                    (format) => formatLabels(itemTypes.data)[format] ?? format,
                  )
                  .join(", ") || "—"}
              </PropertyRow>
              {has("date_started") && (
                <PropertyRow
                  name="started"
                  label={nameOf("date_started")}
                  icon={<CalendarPlus aria-hidden="true" />}
                  onEdit={() => setDialog("opinion")}
                >
                  {entry.date_started ?? "—"}
                </PropertyRow>
              )}
              {has("date_finished") && (
                <PropertyRow
                  name="finished"
                  label={nameOf("date_finished")}
                  icon={<CalendarCheck aria-hidden="true" />}
                  onEdit={() => setDialog("opinion")}
                >
                  {entry.date_finished ?? "—"}
                </PropertyRow>
              )}
              {has("reread_count") && (
                <PropertyRow
                  name="rereads"
                  label={nameOf("reread_count")}
                  icon={<Repeat aria-hidden="true" />}
                  onEdit={() => setDialog("opinion")}
                >
                  {entry.reread_count}
                </PropertyRow>
              )}
              {progress && (
                <PropertyRow
                  name="progress"
                  label={progress.label}
                  icon={<Gauge aria-hidden="true" />}
                  onEdit={() => setDialog("opinion")}
                >
                  {entry.progress == null
                    ? "—"
                    : typeof progressTotal === "number"
                      ? `${entry.progress} / ${progressTotal} ${progress.unit_label}s`
                      : `${entry.progress} ${progress.unit_label}s`}
                </PropertyRow>
              )}
              {/* Editable where it is read. The owner's complaint was distance:
                  shelf membership lived inside a dialog named after something
                  else, and creating a shelf was a whole route. */}
              <PropertyRow
                name="shelves"
                label="Shelves"
                icon={<Bookmark aria-hidden="true" />}
              >
                <ShelfPicker
                  current={entry.shelves}
                  available={shelves.data ?? []}
                  onChange={async (shelfIds) => {
                    await update.mutateAsync(() =>
                      patchEntry(entry.id, { shelf_ids: shelfIds }),
                    );
                  }}
                  onCreate={handleCreateShelf}
                />
              </PropertyRow>
            </dl>
            {entry.notes && (
              // The note as a callout, marked with the arch (Sprint 092).
              <div className="mt-4 flex gap-3 rounded-lg bg-muted/60 p-4">
                <svg
                  aria-hidden="true"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  className="mt-1 shrink-0 text-muted-foreground"
                >
                  <path d="M4 21V10a8 8 0 0 1 16 0v11" />
                  <circle cx="12" cy="11" r="2" fill="#fbbf24" stroke="none" />
                </svg>
                <div>
                  <p className="text-xs text-muted-foreground">Notes</p>
                  <p className="mt-1 whitespace-pre-wrap font-display text-lg italic text-foreground">
                    {entry.notes}
                  </p>
                </div>
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
          </Panel>

          {/* Files, at the weight of the thing it is.
              It was a small outline button in the corner of Edition facts, which
              is where a footnote goes, not where an attachment goes: what is
              attached to an edition is the edition's, but *attaching* one is
              something the reader does, like editing an opinion. Its own region,
              between the two, keeps the control beside the list it produces --
              which putting the button under the cover would not. */}
          <Panel className="mt-6" aria-label="Files" bodyClassName="p-4">
            <Attachments itemId={item.id} />
          </Panel>

          {/* Edition facts region */}
          <Panel
            className="mt-6"
            aria-labelledby="edition-facts-heading"
            heading="Edition facts"
            headingId="edition-facts-heading"
          >
            <dl className="grid grid-cols-2 gap-4">
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
          </Panel>

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
        onSave={(values) =>
          update
            .mutateAsync(() =>
              patchEntry(entry.id, {
                status: values.status,
                score: values.score,
                notes: values.notes,
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
                // `""` is "not recorded" and must reach the server as null, while
                // `"0"` is a recorded zero. `Number("")` is `0`, so the empty check
                // comes first — the reread line above cannot be copied here.
                ...(progress
                  ? {
                      progress:
                        values.progress === "" ? null : Number(values.progress),
                    }
                  : {}),
              }),
            )
            .then(() => undefined)
        }
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
