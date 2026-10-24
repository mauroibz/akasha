import {
  Bookmark,
  CalendarCheck,
  CalendarPlus,
  CircleDot,
  Gauge,
  Handshake,
  History,
  MapPin,
  Repeat,
  Shapes,
  Star,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import type { FieldSpec, FillResult, LibraryEntry } from "@/api/library";
import {
  deleteEntry,
  fillItem,
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
import { LoanRow, LocationRow } from "@/features/house/HouseRows";
import { HowFarDialog } from "@/features/progress/HowFarDialog";
import { isAbandoned, localDay } from "@/features/progress/outline";
import { askStill, isFinished, statusWith } from "@/features/rescore/rescore";
import { ScoreHistoryRow } from "@/features/rescore/ScoreHistoryRow";
import { FinishDialog } from "@/features/finish/FinishDialog";
import { StillDialog } from "@/features/rescore/StillDialog";
import { ProgressTracker } from "@/features/progress/ProgressTracker";
import { RefileDialog } from "@/features/detail/RefileDialog";
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
    <div data-fact={name} className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
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

/** "a", "a and b", "a, b and c". */
function listed(words: string[]): string {
  if (words.length < 2) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

/**
 * What a fill did, in a sentence (Sprint 109): the fields it wrote by the domain's
 * own names for them, or why it wrote none.
 */
function fillMessage(result: FillResult, fields: FieldSpec[]): string {
  if (result.filled.length) {
    const names = result.filled.map(
      (name) =>
        fields.find((field) => field.name === name)?.label.toLowerCase() ??
        name,
    );
    return `Filled ${listed(names)}`;
  }
  if (result.queued) return "Looking it up; this fills in the background";
  if (result.provider) return `Nothing new from ${result.provider}`;
  return "There is nothing to look this up by yet. Add an identifier in Edit metadata.";
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
    | "opinion"
    | "metadata"
    | "refresh"
    | "delete"
    | "cover"
    | "refile"
    | "again"
    | null
  >(null);
  const [error, setError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  // The entry just dropped, while the page asks how far it got (DEC-172).
  const [asking, setAsking] = useState<LibraryEntry | null>(null);
  // Finishing what is under way, in one sheet (Sprint 123).
  const [finishing, setFinishing] = useState(false);
  // Finished again with a score: "Still an 8?" (Sprint 115).
  const [still, setStill] = useState<{
    entry: LibraryEntry;
    again?: boolean;
  } | null>(null);
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
  const fill = useMutation({
    mutationFn: (itemId: number) => fillItem(itemId),
    onSuccess: (result) => {
      setError("");
      toast(fillMessage(result, fieldsOf(result.item.type)));
      void cache.invalidateQueries({ queryKey: queryKeys.entry(entryId) });
      void cache.invalidateQueries({ queryKey: queryKeys.library.all });
    },
    onError: (value: Error) => setError(value.message),
  });
  const fieldsOf = (type: string) =>
    itemTypes.data?.find((candidate) => candidate.id === type)?.fields ?? [];
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
  // Facts the item has, and how many it lacks: an empty field is a count and an
  // offer to fill it, not a row of dashes (Sprint 109).
  const isEmpty = (field: FieldSpec) =>
    formatFact(item.metadata[field.name], field) === "—";
  const shownFields = inlineFields.filter((field) => !isEmpty(field));
  const missing = [...inlineFields, ...blockFields]
    .filter(isEmpty)
    .map((field) => field.label.toLowerCase());
  const identifiers = Object.entries(item.identifiers);
  // An ordered list of structured rows is neither a fact nor a paragraph, so it
  // gets its own region rather than being joined into one line (a tracklist). The
  // field the progress tracker draws its parts from is drawn there instead.
  const partsField = progressFor(item.type, itemTypes.data)?.parts_field;
  const rowFields = fields.filter(
    (field) => field.type === "rows" && field.name !== partsField,
  );
  const editableFields = fields.filter((field) => field.type !== "rows");
  const has = (field: EntryFieldName) =>
    hasEntryField(item.type, itemTypes.data, field);
  // The domain's own word for the field, not a book's (technical spec 6.6).
  const nameOf = (field: EntryFieldName) =>
    entryFieldLabel(item.type, itemTypes.data, field);

  // Another time through (Sprint 115). A domain with a status for "under way" goes
  // back to it, with the dates of the last pass cleared; one without (a film) has no
  // pass to begin, so watching it again is answered at once.
  const underWay = statusWith(item.type, itemTypes.data, "in_progress");
  const inProgress = underWay !== null && entry.status === underWay;
  function beginAgain() {
    if (underWay) setDialog("again");
    else setStill({ entry, again: true });
  }
  function startAgain() {
    if (!underWay) return;
    update.mutate(() =>
      patchEntry(entry.id, {
        status: underWay,
        ...(has("date_started") ? { date_started: localDay(new Date()) } : {}),
        ...(has("date_finished") ? { date_finished: null } : {}),
        ...(has("reread_count")
          ? { reread_count: entry.reread_count + 1 }
          : {}),
        // A typed count clears the marks (DEC-171): the new pass starts unlit.
        ...(entry.progress !== null ? { progress: 0 } : {}),
      }),
    );
  }

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
      <div className="mt-8 grid grid-cols-1 gap-8 md:grid-cols-[240px_1fr]">
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
              <ScoreHistoryRow
                entryId={entry.id}
                icon={<History aria-hidden="true" />}
              />
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
              <LocationRow entry={entry} icon={<MapPin aria-hidden="true" />} />
              <LoanRow entry={entry} icon={<Handshake aria-hidden="true" />} />
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
              {/* The progress row is the tracker: one control for one number
                  (DEC-171, the owner's note on the first look). */}
              <ProgressTracker
                entry={entry}
                types={itemTypes.data}
                icon={<Gauge aria-hidden="true" />}
                onFinished={(saved) => {
                  // The last light finishes the pass (DEC-175): with a score, ask.
                  if (saved.score !== null) setStill({ entry: saved });
                }}
              />
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
              {/* Under way, the next thing to do is finish it (Sprint 123): after
               *Start again* there was no way to finish but the status menu. */}
              {inProgress && (
                <Button
                  className="rounded-full px-5"
                  onClick={() => setFinishing(true)}
                >
                  Finished
                </Button>
              )}
              <Button
                variant={inProgress ? "outline" : "default"}
                className="rounded-full px-5"
                onClick={() => setDialog("opinion")}
              >
                Edit opinion
              </Button>
              {isFinished(entry, itemTypes.data) && entry.score !== null && (
                <Button
                  variant="outline"
                  className="rounded-full px-5"
                  onClick={beginAgain}
                >
                  Start again
                </Button>
              )}
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
              {shownFields.map((field) => (
                <Fact key={field.name} name={field.name} label={field.label}>
                  {formatFact(item.metadata[field.name], field)}
                </Fact>
              ))}
              {identifiers.length > 0 && (
                <Fact name="identifiers" label="Identifiers">
                  {identifiers.map(([k, v]) => (
                    <span key={k} className="block text-sm">
                      {k}: {v}
                    </span>
                  ))}
                </Fact>
              )}
              {item.sources.length > 0 && (
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
                </Fact>
              )}
            </dl>
            {missing.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-border pt-4">
                <p className="text-sm text-muted-foreground">
                  Missing:{" "}
                  {missing.length > 3
                    ? `${missing.slice(0, 2).join(", ")} and ${missing.length - 2} more`
                    : listed(missing)}
                </p>
                <Button
                  variant="secondary"
                  size="sm"
                  className="rounded-full px-4"
                  disabled={fill.isPending}
                  onClick={() => fill.mutate(item.id)}
                >
                  {fill.isPending ? "Filling…" : "Fill from provider"}
                </Button>
              </div>
            )}
            {blockFields.map((field) => {
              const value = formatFact(item.metadata[field.name], field);
              return value === "—" ? null : (
                <div key={field.name} className="mt-4">
                  <p className="text-xs text-muted-foreground">{field.label}</p>
                  <p className="mt-1 whitespace-pre-wrap break-words text-foreground">
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
              <Button
                variant="outline"
                className="rounded-full px-5"
                onClick={() => setDialog("refile")}
              >
                Move to another library…
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
        onSave={(values) => {
          return update
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
                // No progress: the progress row changes it, never this dialog
                // (DEC-174), so saving a score cannot touch the marks.
              }),
            )
            .then((saved) => {
              // Dropped just now: ask how far (DEC-172).
              const dropped =
                values.status !== entry.status &&
                isAbandoned(item.type, values.status, itemTypes.data);
              if (dropped) setAsking(saved as LibraryEntry);
              // Finished again, with a score: ask whether it holds (Sprint 115).
              else if (askStill(entry, saved as LibraryEntry, itemTypes.data))
                setStill({ entry: saved as LibraryEntry });
            });
        }}
      />

      <HowFarDialog
        entry={asking}
        types={itemTypes.data}
        onClose={() => setAsking(null)}
      />

      <FinishDialog
        entry={finishing ? entry : null}
        types={itemTypes.data}
        onClose={() => setFinishing(false)}
      />

      <StillDialog
        entry={still?.entry ?? null}
        again={still?.again}
        onClose={() => setStill(null)}
      />

      {/* Another pass (Sprint 115): the dates of this one clear, the score and its
          history stay, and finishing will ask whether the score still holds. */}
      <AlertDialog
        open={dialog === "again"}
        onOpenChange={(open) => setDialog(open ? "again" : null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Start {item.title} again?</AlertDialogTitle>
            <AlertDialogDescription>
              {entry.date_finished
                ? `Finished (${entry.date_finished}) is cleared`
                : "Finished stays empty"}
              {entry.progress !== null
                ? " and progress starts from nothing"
                : ""}
              . Your score and how it changed stay, and finishing again will ask
              whether it still holds.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(buttonVariants(), "rounded-full px-5")}
              onClick={() => startAgain()}
            >
              Start again
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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

      <RefileDialog
        open={dialog === "refile"}
        onOpenChange={(open) => setDialog(open ? "refile" : null)}
        entryId={entry.id}
        title={item.title}
        itemType={item.type}
        onMoved={(moved) => {
          void cache.invalidateQueries({
            queryKey: queryKeys.library.all,
          });
          cache.removeQueries({ queryKey: queryKeys.entry(entry.id) });
          toast.success(`Moved ${moved.item.title}`);
          navigate(`/books/${moved.id}`, { replace: true, state: { from } });
        }}
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
