import { zodResolver } from "@hookform/resolvers/zod";
import { m } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  createEntry,
  getShelves,
  NearMatchError,
  searchCandidates,
  type ManualItem,
  type SearchCandidate,
} from "@/api/add";
import { CoverImage } from "@/components/CoverImage";
import { useMotionPresets } from "@/lib/motion";
import { ProviderHealthNotice } from "@/components/ProviderHealthNotice";
import { ScorePicker } from "@/components/ScorePicker";
import { StatusSelect } from "@/components/StatusSelect";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Field } from "@/features/detail/Field";
import {
  manualBookSchema,
  optionalInt,
  splitList,
  type ManualBookValues,
} from "@/features/detail/schemas";
import type { EntryStatus, ItemType } from "@/api/library";
import { getItemTypes } from "@/api/library";
import { statusesFor } from "@/features/library/labels";
import { cn } from "@/lib/utils";

export function AddPage() {
  const [query, setQuery] = useState("");
  // Which domain is being searched. Not a filter over one result set: it decides
  // which providers are asked at all (DEC-052 seam 6).
  const [itemType, setItemType] = useState("book");
  const [itemTypes, setItemTypes] = useState<ItemType[]>([]);
  const [results, setResults] = useState<SearchCandidate[]>([]);
  const presets = useMotionPresets();
  // Identity of the committed result set, so a new search re-staggers and a
  // re-render of the same results does not.
  const resultsKey = results.map((row) => row.source_id).join("|");
  const [selected, setSelected] = useState<SearchCandidate | null>(null);
  const [manual, setManual] = useState(false);
  // Seeded from the domain rather than fixed: a book is added `read` and a record
  // is added `owned`, and the API refuses the other domain's default outright.
  const [status, setStatus] = useState<EntryStatus>("read");
  const [score, setScore] = useState("");
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  const [near, setNear] = useState<number[]>([]);
  const [pending, setPending] = useState(false);
  const [shelves, setShelves] = useState<Array<{ id: number; name: string }>>(
    [],
  );
  const [shelfIds, setShelfIds] = useState<number[]>([]);
  const titleRef = useRef<HTMLInputElement | null>(null);
  const searchRequestId = useRef(0);
  const statusRef = useRef<HTMLButtonElement>(null);
  const nearRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();
  useEffect(() => {
    if (query.trim().length < 2) return setResults([]);
    // Two guards, and both earn their place. The request id decides which
    // response is allowed to land, so a slow first search can never overwrite a
    // fast second one. The abort actually stops the first one: provider search
    // takes about five seconds, so without it a few keystrokes leave several
    // multi-second requests running against a rate-limited free API for results
    // that will be thrown away (technical spec section 8).
    const requestId = ++searchRequestId.current;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setPending(true);
      setError("");
      void searchCandidates(query, itemType, controller.signal)
        .then((value) => {
          if (searchRequestId.current !== requestId) return;
          setResults(value.items);
          setWarning(value.warning ?? "");
        })
        .catch((e: Error) => {
          // An abort is this effect's own cleanup, not a failure the reader
          // needs to be told about.
          if (e.name === "AbortError") return;
          if (searchRequestId.current !== requestId) return;
          setError(e.message);
          setWarning(
            itemType === "book"
              ? "You can still enter this book manually."
              : "Try again in a moment.",
          );
        })
        .finally(() => {
          if (searchRequestId.current !== requestId) return;
          setPending(false);
        });
    }, 300);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, itemType]);
  useEffect(() => {
    void getShelves()
      .then(setShelves)
      .catch(() => undefined);
  }, []);
  // The domains come from the server, so this screen never enumerates them itself.
  useEffect(() => {
    void getItemTypes()
      .then((types) => {
        setItemTypes(types);
        // The registry arrives after the first render, so the initial default
        // comes from it rather than staying on the book-era literal below.
        const current = types.find((type) => type.id === itemType);
        if (current) setStatus(current.default_status);
      })
      .catch(() => undefined);
    // Runs once: the domain chooser sets the status itself when it changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (manual) titleRef.current?.focus();
  }, [manual]);
  useEffect(() => {
    if (selected) statusRef.current?.focus();
  }, [selected]);
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
              source: selected!.source,
              source_id: selected!.source_id,
              source_refs: selected!.source_refs,
            }),
        status,
        score: score ? Number(score) : undefined,
        shelf_ids: shelfIds,
        confirm_near_match: confirmed,
      });
      if (result.near_matches.length && !confirmed) {
        setNear(result.near_matches);
        setPending(false);
        return;
      }
      if (result.already_exists) {
        toast("Already in your library", {
          description: "Opened the entry you already have.",
        });
        navigate(`/books/${result.entry.id}`);
      } else {
        toast.success("Book added");
        // The destination highlights the new row. This travels as router state
        // rather than sessionStorage so a reload does not resurrect a stale
        // highlight, and so the handoff is visible in the navigation itself.
        navigate("/", { state: { newEntryId: result.entry.id } });
      }
    } catch (e) {
      if (e instanceof NearMatchError) {
        setNear(e.entryIds);
        setPending(false);
        return;
      }
      setError(e instanceof Error ? e.message : "Book could not be added");
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
  const editing = manual || selected;
  const searchLabel = itemType === "book" ? "Search books" : "Search albums";
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <Button variant="ghost" className="px-0" onClick={() => navigate("/")}>
        ← Library
      </Button>
      <h1 className="mt-6 text-4xl font-semibold">Add to your library</h1>
      {!editing && (
        <>
          {itemTypes.length > 1 && (
            <div
              role="radiogroup"
              aria-label="What are you adding?"
              className="mt-6 inline-flex rounded-full bg-surface p-1"
            >
              {itemTypes.map((choice) => (
                <button
                  key={choice.id}
                  type="button"
                  role="radio"
                  aria-checked={itemType === choice.id}
                  className={cn(
                    "rounded-full px-5 py-2 text-sm font-medium transition-colors",
                    itemType === choice.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  onClick={() => {
                    setItemType(choice.id);
                    setStatus(choice.default_status);
                    setResults([]);
                    setManual(false);
                  }}
                >
                  {choice.label}
                </button>
              ))}
            </div>
          )}
          <label className="mt-4 block">
            <span className="sr-only">{searchLabel}</span>
            <Input
              autoFocus
              role="searchbox"
              aria-label={searchLabel}
              className="h-12 rounded-full bg-surface px-5"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                itemType === "book"
                  ? "Title, author, ISBN, or URL"
                  : "Album or artist"
              }
            />
          </label>
          <ProviderHealthNotice />
          {pending && <p role="status">Searching metadata providers…</p>}
          {error && <p role="alert">{error}</p>}
          {warning && <p role="status">{warning}</p>}
          {/* Results arrive in sequence rather than all at once. The delay
              stops growing after a handful of cards: a twenty-result search
              would otherwise take most of a second to finish arriving, which
              reads as slow rather than as considered. */}
          <m.section
            aria-label="Search results"
            className="mt-6 grid gap-3 sm:grid-cols-2"
            key={resultsKey}
            initial="hidden"
            animate="show"
          >
            {results.map((row, index) => (
              <m.button
                key={`${row.source}:${row.source_id}`}
                variants={presets.staggerItem(index)}
                className="min-h-28 rounded-2xl bg-surface p-4 text-left focus-ring"
                onClick={() => setSelected(row)}
              >
                <span className="grid grid-cols-[64px_1fr] gap-3">
                  <CoverImage
                    src={row.cover_url}
                    alt={`Cover of ${row.title}`}
                    className="aspect-[2/3] w-16"
                  />
                  <span>
                    <strong>{row.title}</strong>
                    <span className="mt-1 block text-muted-foreground">
                      {row.credit ??
                        (row.creators.join(", ") || "Unknown creator")}
                    </span>
                    <span className="block text-sm">
                      Edition year: {row.year ?? "unknown"}
                      {row.metadata?.publisher
                        ? ` · ${row.metadata.publisher}`
                        : ""}
                      {row.language ? ` · ${row.language}` : ""}
                    </span>
                    {row.original_year && row.original_year !== row.year && (
                      <span className="block text-sm">
                        Originally published: {row.original_year}
                      </span>
                    )}
                    <span className="text-xs uppercase text-primary">
                      {row.source}
                    </span>
                  </span>
                </span>
              </m.button>
            ))}
            {/* Part of the same list, and the option a reader reaches for last,
                so it arrives last rather than ahead of the results it follows. */}
            <m.button
              variants={presets.staggerItem(results.length)}
              className="min-h-28 rounded-2xl border border-dashed border-border p-4 text-left focus-ring"
              onClick={() => setManual(true)}
            >
              None of these — enter manually
            </m.button>
          </m.section>
        </>
      )}
      {editing && (
        // Enter only, and never `mode="wait"`: the form focuses its status
        // control on mount, and delaying that mount behind an exit animation
        // moves the keyboard flow's first focus a tenth of a second late.
        <m.form
          className="mt-8 space-y-5"
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
              <Field
                id="manual-title"
                label="Title"
                error={errors.title?.message}
              >
                {(props) => (
                  <Input
                    {...props}
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
                {(props) => (
                  <Input
                    {...props}
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
                {(props) => (
                  <Input
                    {...props}
                    className="h-11"
                    {...form.register("subtitle")}
                  />
                )}
              </Field>
              <Field id="manual-year" label="Year" error={errors.year?.message}>
                {(props) => (
                  <Input
                    {...props}
                    type="number"
                    className="h-11"
                    {...form.register("year")}
                  />
                )}
              </Field>
              <Field id="manual-isbn" label="ISBN" error={errors.isbn?.message}>
                {(props) => (
                  <Input
                    {...props}
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
              {selected && (
                <CoverImage
                  src={selected.cover_url}
                  alt={`Cover of ${selected.title}`}
                  className="aspect-[2/3] w-[72px] shrink-0 rounded-lg"
                />
              )}
              <div>
                <h2 className="text-2xl font-semibold">{selected?.title}</h2>
                <p>{selected?.credit ?? selected?.creators.join(", ")}</p>
              </div>
            </div>
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
          {shelves.length > 0 && (
            <fieldset>
              <legend>Shelves</legend>
              <div className="flex flex-wrap gap-3">
                {shelves.map((shelf) => (
                  <div key={shelf.id} className="flex items-center gap-2">
                    <Checkbox
                      id={`shelf-${shelf.id}`}
                      checked={shelfIds.includes(shelf.id)}
                      onCheckedChange={(checked) =>
                        setShelfIds((old) =>
                          checked
                            ? [...old, shelf.id]
                            : old.filter((id) => id !== shelf.id),
                        )
                      }
                    />
                    <Label htmlFor={`shelf-${shelf.id}`}>{shelf.name}</Label>
                  </div>
                ))}
              </div>
            </fieldset>
          )}
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
                onClick={() => navigate(`/books/${near[0]}`)}
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
      )}
    </main>
  );
}
