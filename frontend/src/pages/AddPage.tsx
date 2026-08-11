import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  createEntry,
  getShelves,
  NearMatchError,
  searchBooks,
  type ManualItem,
  type SearchCandidate,
} from "@/api/add";
import { CoverImage } from "@/components/CoverImage";
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
import type { EntryStatus } from "@/api/library";

export function AddPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchCandidate[]>([]);
  const [selected, setSelected] = useState<SearchCandidate | null>(null);
  const [manual, setManual] = useState(false);
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
    const requestId = ++searchRequestId.current;
    const timer = window.setTimeout(() => {
      setPending(true);
      setError("");
      void searchBooks(query)
        .then((value) => {
          if (searchRequestId.current !== requestId) return;
          setResults(value.items);
          setWarning(value.warning ?? "");
        })
        .catch((e: Error) => {
          if (searchRequestId.current !== requestId) return;
          setError(e.message);
          setWarning("You can still enter this book manually.");
        })
        .finally(() => {
          if (searchRequestId.current !== requestId) return;
          setPending(false);
        });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    void getShelves()
      .then(setShelves)
      .catch(() => undefined);
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
          authors: splitList(values.authors),
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
      authors: "",
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
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <Button variant="ghost" className="px-0" onClick={() => navigate("/")}>
        ← Library
      </Button>
      <h1 className="mt-6 text-4xl font-semibold">Add a book</h1>
      {!editing && (
        <>
          <label className="mt-8 block">
            <span className="sr-only">Search books</span>
            <Input
              autoFocus
              role="searchbox"
              aria-label="Search books"
              className="h-12 rounded-full bg-surface px-5"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Title, author, ISBN, or URL"
            />
          </label>
          <ProviderHealthNotice />
          {pending && <p role="status">Searching metadata providers…</p>}
          {error && <p role="alert">{error}</p>}
          {warning && <p role="status">{warning}</p>}
          <section
            aria-label="Search results"
            className="mt-6 grid gap-3 sm:grid-cols-2"
          >
            {results.map((row) => (
              <button
                key={`${row.source}:${row.source_id}`}
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
                      {row.authors.join(", ") || "Unknown author"}
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
              </button>
            ))}
            <button
              className="min-h-28 rounded-2xl border border-dashed border-border p-4 text-left focus-ring"
              onClick={() => setManual(true)}
            >
              None of these — enter manually
            </button>
          </section>
        </>
      )}
      {editing && (
        <form
          className="mt-8 space-y-5"
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
                id="manual-authors"
                label="Authors, comma separated"
                error={errors.authors?.message}
              >
                {(props) => (
                  <Input
                    {...props}
                    className="h-11"
                    {...form.register("authors")}
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
            <div>
              <h2 className="text-2xl font-semibold">{selected?.title}</h2>
              <p>{selected?.authors.join(", ")}</p>
            </div>
          )}
          <div className="flex flex-wrap gap-4">
            <div>
              <span className="mb-1 block text-sm">Status</span>
              <StatusSelect
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
        </form>
      )}
    </main>
  );
}
