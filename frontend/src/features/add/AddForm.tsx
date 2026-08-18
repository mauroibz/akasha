import { zodResolver } from "@hookform/resolvers/zod";
import { m } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";

import {
  createEntry,
  getShelves,
  NearMatchError,
  previewCandidate,
  type ManualItem,
  type SearchCandidate,
} from "@/api/add";
import { createShelf, type ShelfWithCount } from "@/api/shelves";
import type { EntryStatus, ItemType } from "@/api/library";
import { CoverImage } from "@/components/CoverImage";
import { ScorePicker } from "@/components/ScorePicker";
import { StatusSelect } from "@/components/StatusSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CandidateFacts } from "@/features/add/CandidateFacts";
import { Field } from "@/features/detail/Field";
import {
  manualBookSchema,
  optionalInt,
  splitList,
  type ManualBookValues,
} from "@/features/detail/schemas";
import { FormatPicker } from "@/features/library/FormatPicker";
import { ShelfPicker } from "@/features/shelves/ShelfPicker";
import {
  formatsFor,
  hasEntryField,
  labelFor,
  statusesFor,
} from "@/features/library/labels";
import { useMotionPresets } from "@/lib/motion";

export interface AddFormProps {
  /** The domain being added to. Decides the vocabulary, the fields and the copy. */
  itemType: string;
  itemTypes: ItemType[];
  /**
   * What is being added: a candidate the reader picked from provider results, or a
   * hand-typed item no provider has. The two differ only in what the top of the form
   * renders and in what the request carries; everything below is one opinion form.
   */
  candidate: SearchCandidate | null;
  manual: boolean;
  onAdded: (entryId: number, alreadyExists: boolean) => void;
  onOpenExisting: (entryId: number) => void;
}

/**
 * The confirm step of the add flow, as Sprint 027's second pass built it.
 *
 * It is a component rather than part of a screen because Sprint 029 hosts it in two
 * places: `/add` renders it for manual entry, and `/` renders it in a dialog over the
 * library once a provider result is chosen. Nothing here knows which — the only
 * difference a host makes is what it does with `onAdded`.
 */
export function AddForm(props: AddFormProps) {
  const { itemType, itemTypes, candidate, manual } = props;
  const presets = useMotionPresets();
  const [status, setStatus] = useState<EntryStatus>("read");
  const [score, setScore] = useState("");
  const [error, setError] = useState("");
  const [near, setNear] = useState<number[]>([]);
  const [pending, setPending] = useState(false);
  const [shelves, setShelves] = useState<ShelfWithCount[]>([]);
  const [shelfIds, setShelfIds] = useState<number[]>([]);
  // The candidate as fetched in full, when the reader asked for it. Kept beside
  // `candidate` rather than replacing it, so the identity that was clicked stays the
  // thing being added even if the provider answers with a different shape.
  const [fullRecord, setFullRecord] = useState<SearchCandidate | null>(null);
  const [loadingFull, setLoadingFull] = useState(false);
  const [previewError, setPreviewError] = useState("");
  // The rest of the opinion, set while adding rather than by adding and then
  // immediately opening the edit dialog.
  const [notes, setNotes] = useState("");
  const [formats, setFormats] = useState<string[]>([]);
  const [dateStarted, setDateStarted] = useState("");
  const [dateFinished, setDateFinished] = useState("");
  const [rereadCount, setRereadCount] = useState("");
  const titleRef = useRef<HTMLInputElement | null>(null);
  const statusRef = useRef<HTMLButtonElement>(null);
  const nearRef = useRef<HTMLButtonElement>(null);

  // Asked of the domain rather than branched on the type: a record has no reread
  // count and no started/finished dates (DEC-057).
  const has = (field: "date_started" | "date_finished" | "reread_count") =>
    hasEntryField(itemType, itemTypes, field);
  const domainFormats = formatsFor(itemType, itemTypes);

  useEffect(() => {
    void getShelves()
      .then(setShelves)
      .catch(() => undefined);
  }, []);
  // The domain's own default, not a literal: a book is added `read` and a record
  // `owned`, and the API refuses the other domain's default outright.
  useEffect(() => {
    const current = itemTypes.find((type) => type.id === itemType);
    if (current) setStatus(current.default_status);
  }, [itemType, itemTypes]);
  useEffect(() => {
    if (manual) titleRef.current?.focus();
  }, [manual]);
  useEffect(() => {
    if (candidate) statusRef.current?.focus();
    // A record fetched for the previous selection describes a different edition.
    setFullRecord(null);
    setPreviewError("");
  }, [candidate]);
  useEffect(() => {
    if (near.length) nearRef.current?.focus();
  }, [near]);

  async function submit(values: ManualBookValues, confirmed = false) {
    if (near.length && !confirmed) return;
    setPending(true);
    setError("");
    const item: ManualItem | undefined = manual
      ? {
          title: values.title.trim(),
          subtitle: values.subtitle || undefined,
          creators: splitList(values.creators),
          year: optionalInt(values.year) ?? undefined,
          isbn: values.isbn || undefined,
        }
      : undefined;
    try {
      const result = await createEntry({
        ...(item
          ? { manual: item, idempotency_key: crypto.randomUUID() }
          : {
              source: candidate!.source,
              source_id: candidate!.source_id,
              source_refs: candidate!.source_refs,
            }),
        status,
        score: score ? Number(score) : undefined,
        shelf_ids: shelfIds,
        // Only what the reader actually filled in, and only fields this domain
        // has: the API refuses a reread count on a record with a 422, and it is
        // right to (DEC-057).
        ...(notes.trim() ? { notes: notes.trim() } : {}),
        ...(formats.length ? { formats } : {}),
        ...(has("date_started") && dateStarted
          ? { date_started: dateStarted }
          : {}),
        ...(has("date_finished") && dateFinished
          ? { date_finished: dateFinished }
          : {}),
        ...(has("reread_count") && rereadCount
          ? { reread_count: Number(rereadCount) }
          : {}),
        confirm_near_match: confirmed,
      });
      if (result.near_matches.length && !confirmed) {
        setNear(result.near_matches);
        setPending(false);
        return;
      }
      props.onAdded(result.entry.id, result.already_exists);
    } catch (e) {
      if (e instanceof NearMatchError) {
        setNear(e.entryIds);
        setPending(false);
        return;
      }
      setError(
        e instanceof Error
          ? e.message
          : `${labelFor(itemType, itemTypes)} could not be added`,
      );
      setPending(false);
    }
  }

  const form = useForm<ManualBookValues>({
    resolver: zodResolver(manualBookSchema),
    defaultValues: {
      title: "",
      creators: "",
      subtitle: "",
      year: "",
      isbn: "",
    },
  });
  const errors = form.formState.errors;
  // A chosen search result carries its own metadata and renders no fields, so
  // running the manual-entry schema over it would reject an add that has
  // nothing to validate.
  const submitForm = manual
    ? form.handleSubmit((values) => submit(values))
    : () => submit(form.getValues());

  return (
    // Enter only, and never `mode="wait"`: the form focuses its status
    // control on mount, and delaying that mount behind an exit animation
    // moves the keyboard flow's first focus a tenth of a second late.
    <m.form
      className="space-y-5"
      initial={presets.formEnter.initial}
      animate={presets.formEnter.animate}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submitForm(e);
      }}
    >
      {manual ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="manual-title" label="Title" error={errors.title?.message}>
            {(fieldProps) => (
              <Input
                {...fieldProps}
                className="h-11"
                {...form.register("title")}
                ref={(node) => {
                  form.register("title").ref(node);
                  titleRef.current = node;
                }}
              />
            )}
          </Field>
          <Field
            id="manual-creators"
            label="Creators, comma separated"
            error={errors.creators?.message}
          >
            {(fieldProps) => (
              <Input
                {...fieldProps}
                className="h-11"
                {...form.register("creators")}
              />
            )}
          </Field>
          <Field
            id="manual-subtitle"
            label="Subtitle"
            error={errors.subtitle?.message}
          >
            {(fieldProps) => (
              <Input
                {...fieldProps}
                className="h-11"
                {...form.register("subtitle")}
              />
            )}
          </Field>
          <Field id="manual-year" label="Year" error={errors.year?.message}>
            {(fieldProps) => (
              <Input
                {...fieldProps}
                type="number"
                className="h-11"
                {...form.register("year")}
              />
            )}
          </Field>
          <Field id="manual-isbn" label="ISBN" error={errors.isbn?.message}>
            {(fieldProps) => (
              <Input
                {...fieldProps}
                className="h-11"
                {...form.register("isbn")}
              />
            )}
          </Field>
        </div>
      ) : (
        // The card the reader just clicked, carried to the top of the
        // form: the selection stays visible instead of being replaced by a
        // bare title.
        <div className="flex items-start gap-4">
          {candidate && (
            <CoverImage
              src={candidate.cover_url}
              alt={`Cover of ${candidate.title}`}
              className="aspect-[2/3] w-[72px] shrink-0 rounded-lg"
            />
          )}
          <div>
            <h2 className="text-2xl font-semibold">{candidate?.title}</h2>
            <p>{candidate?.credit ?? candidate?.creators.join(", ")}</p>
          </div>
        </div>
      )}
      {/* Everything the search already returned, for free, plus whatever the
          on-demand fetch added on top of it. */}
      {candidate && (
        <>
          <CandidateFacts
            candidate={fullRecord ?? candidate}
            fields={
              itemTypes.find((type) => type.id === itemType)?.fields ?? []
            }
          />
          {!fullRecord && (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-full"
                disabled={loadingFull}
                onClick={() => {
                  setLoadingFull(true);
                  setPreviewError("");
                  void previewCandidate(candidate.source, candidate.source_id)
                    .then(setFullRecord)
                    .catch((e: Error) => setPreviewError(e.message))
                    .finally(() => setLoadingFull(false));
                }}
              >
                {loadingFull ? "Loading…" : "Load full details"}
              </Button>
              {/* Said once, in plain terms: this is a live request against a
                  rate-limited provider, so it is asked for rather than made on
                  every click through a result list. */}
              <span className="text-xs text-muted-foreground">
                Asks the provider for the description and the rest
              </span>
            </div>
          )}
          {previewError && (
            <p role="alert" className="text-sm text-destructive">
              {previewError}
            </p>
          )}
        </>
      )}
      <div className="flex flex-wrap gap-4">
        <div>
          <span className="mb-1 block text-sm">Status</span>
          <StatusSelect
            statuses={statusesFor(itemType, itemTypes)}
            triggerRef={statusRef}
            value={status}
            onValueChange={setStatus}
            label="Status"
            className="w-44"
          />
        </div>
        <div>
          <span className="mb-1 block text-sm">Score</span>
          <ScorePicker
            value={score ? Number(score) : null}
            onChange={(v) => setScore(v ? String(v) : "")}
          />
        </div>
      </div>
      {/* The same control as the detail page: find a shelf as you type, or
          create one on the spot. It holds the choice locally until the entry
          it belongs to exists. */}
      <div>
        <span className="mb-2 block text-sm">Shelves</span>
        <ShelfPickerHost
          shelves={shelves}
          shelfIds={shelfIds}
          onChange={setShelfIds}
          onCreated={(created) => setShelves((old) => [...old, created])}
        />
      </div>
      <div className="flex flex-wrap items-end gap-4">
        {domainFormats.length > 0 && (
          <div>
            <span className="mb-1 block text-sm">Format</span>
            <FormatPicker
              formats={domainFormats}
              value={formats}
              onChange={setFormats}
            />
          </div>
        )}
        {has("date_started") && (
          <div>
            <Label htmlFor="add-started" className="mb-1 block text-sm">
              Started
            </Label>
            <Input
              id="add-started"
              type="date"
              className="h-11"
              value={dateStarted}
              onChange={(event) => setDateStarted(event.target.value)}
            />
          </div>
        )}
        {has("date_finished") && (
          <div>
            <Label htmlFor="add-finished" className="mb-1 block text-sm">
              Finished
            </Label>
            <Input
              id="add-finished"
              type="date"
              className="h-11"
              value={dateFinished}
              onChange={(event) => setDateFinished(event.target.value)}
            />
          </div>
        )}
        {has("reread_count") && (
          <div>
            <Label htmlFor="add-rereads" className="mb-1 block text-sm">
              Reread count
            </Label>
            <Input
              id="add-rereads"
              type="number"
              min="0"
              className="h-11 w-28"
              value={rereadCount}
              onChange={(event) => setRereadCount(event.target.value)}
            />
          </div>
        )}
      </div>
      <div>
        <Label htmlFor="add-notes" className="mb-1 block text-sm">
          Notes
        </Label>
        <Textarea
          id="add-notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </div>
      {near.length > 0 && (
        <div role="alert">
          <p>
            A similar edition is already in your library. Add this edition
            anyway?
          </p>
          <Button
            ref={nearRef}
            type="button"
            variant="secondary"
            className="mt-2 rounded-full"
            onClick={() => void submit(form.getValues(), true)}
          >
            Add separate edition
          </Button>{" "}
          <Button
            type="button"
            variant="ghost"
            className="mt-2 rounded-full"
            onClick={() => props.onOpenExisting(near[0])}
          >
            Open existing entry
          </Button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      <Button disabled={pending} className="rounded-full px-6">
        {pending ? "Adding…" : "Add to library"}
      </Button>
    </m.form>
  );
}

/** Split out only to keep the async shelf-creation closure out of the form body. */
function ShelfPickerHost(props: {
  shelves: ShelfWithCount[];
  shelfIds: number[];
  onChange: (ids: number[]) => void;
  onCreated: (created: ShelfWithCount) => void;
}) {
  return (
    <ShelfPicker
      current={props.shelves.filter((shelf) =>
        props.shelfIds.includes(shelf.id),
      )}
      available={props.shelves}
      onChange={async (ids) => props.onChange(ids)}
      onCreate={async (name) => {
        const created = await createShelf(name);
        props.onCreated(created);
        return created;
      }}
    />
  );
}
