import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createEntry,
  getShelves,
  NearMatchError,
  searchBooks,
  type ManualItem,
  type SearchCandidate,
} from "@/api/add";
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
  const titleRef = useRef<HTMLInputElement>(null);
  const statusRef = useRef<HTMLSelectElement>(null);
  const nearRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();
  useEffect(() => {
    if (query.trim().length < 2) return setResults([]);
    const timer = window.setTimeout(() => {
      setPending(true);
      setError("");
      void searchBooks(query)
        .then((value) => {
          setResults(value.items);
          setWarning(value.warning ?? "");
        })
        .catch((e: Error) => {
          setError(e.message);
          setWarning("You can still enter this book manually.");
        })
        .finally(() => setPending(false));
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

  async function submit(form: HTMLFormElement, confirmed = false) {
    if (near.length && !confirmed) return;
    setPending(true);
    setError("");
    const data = new FormData(form);
    const item: ManualItem | undefined = manual
      ? {
          title: String(data.get("title") ?? "").trim(),
          subtitle: String(data.get("subtitle") ?? "") || undefined,
          authors: String(data.get("authors") ?? "")
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean),
          year: data.get("year") ? Number(data.get("year")) : undefined,
          isbn: String(data.get("isbn") ?? "") || undefined,
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
        sessionStorage.setItem("akasha.toast", "Already in your library");
      } else {
        sessionStorage.setItem("akasha.new-entry", String(result.entry.id));
        sessionStorage.setItem("akasha.toast", "Book added");
      }
      navigate(`/books/${result.entry.id}`);
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
  const editing = manual || selected;
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <button className="focus-ring" onClick={() => navigate("/")}>
        ← Library
      </button>
      <h1 className="mt-6 text-4xl font-semibold">Add a book</h1>
      {!editing && (
        <>
          <label className="mt-8 block">
            <span className="sr-only">Search books</span>
            <input
              autoFocus
              role="searchbox"
              aria-label="Search books"
              className="h-12 w-full rounded-full bg-zinc-900 px-5 focus-ring"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Title, author, ISBN, or URL"
            />
          </label>
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
                className="min-h-28 rounded-2xl bg-zinc-900 p-4 text-left focus-ring"
                onClick={() => setSelected(row)}
              >
                <span className="grid grid-cols-[64px_1fr] gap-3">
                  {row.cover_url ? (
                    <img
                      className="aspect-[2/3] w-16 rounded object-cover"
                      src={row.cover_url}
                      alt=""
                    />
                  ) : (
                    <span
                      className="aspect-[2/3] w-16 rounded bg-zinc-800"
                      aria-hidden="true"
                    />
                  )}
                  <span>
                    <strong>{row.title}</strong>
                    <span className="mt-1 block text-zinc-400">
                      {row.authors.join(", ") || "Unknown author"}
                    </span>
                    <span className="block text-sm">
                      Edition year: {row.year ?? "unknown"}
                    </span>
                    {row.original_year && row.original_year !== row.year && (
                      <span className="block text-sm">
                        Originally published: {row.original_year}
                      </span>
                    )}
                    <span className="text-xs uppercase text-fuchsia-400">
                      {row.source}
                    </span>
                  </span>
                </span>
              </button>
            ))}
            <button
              className="min-h-28 rounded-2xl border border-dashed border-zinc-700 p-4 text-left focus-ring"
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
          onSubmit={(e) => {
            e.preventDefault();
            void submit(e.currentTarget);
          }}
        >
          {manual ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <label>
                Title
                <input ref={titleRef} required name="title" className="field" />
              </label>
              <label>
                Authors, comma separated
                <input name="authors" className="field" />
              </label>
              <label>
                Subtitle
                <input name="subtitle" className="field" />
              </label>
              <label>
                Year
                <input
                  name="year"
                  min="0"
                  max="9999"
                  type="number"
                  className="field"
                />
              </label>
              <label>
                ISBN
                <input name="isbn" className="field" />
              </label>
            </div>
          ) : (
            <div>
              <h2 className="text-2xl font-semibold">{selected?.title}</h2>
              <p>{selected?.authors.join(", ")}</p>
            </div>
          )}
          <div className="flex flex-wrap gap-4">
            <label>
              Status
              <select
                ref={statusRef}
                className="field"
                value={status}
                onChange={(e) => setStatus(e.target.value as EntryStatus)}
              >
                <option value="read">Read</option>
                <option value="reading">Reading</option>
                <option value="to_read">To read</option>
                <option value="wishlist">Wishlist</option>
                <option value="dropped">Dropped</option>
                <option value="unsorted">Inbox</option>
              </select>
            </label>
            <label>
              Score
              <input
                className="field"
                type="number"
                min="1"
                max="10"
                value={score}
                onChange={(e) => setScore(e.target.value)}
              />
            </label>
          </div>
          {shelves.length > 0 && (
            <fieldset>
              <legend>Shelves</legend>
              <div className="flex flex-wrap gap-3">
                {shelves.map((shelf) => (
                  <label key={shelf.id}>
                    <input
                      type="checkbox"
                      checked={shelfIds.includes(shelf.id)}
                      onChange={(e) =>
                        setShelfIds((old) =>
                          e.target.checked
                            ? [...old, shelf.id]
                            : old.filter((id) => id !== shelf.id),
                        )
                      }
                    />{" "}
                    {shelf.name}
                  </label>
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
              <button
                ref={nearRef}
                type="button"
                onClick={(e) => void submit(e.currentTarget.form!, true)}
              >
                Add separate edition
              </button>{" "}
              <button
                type="button"
                onClick={() => navigate(`/books/${near[0]}`)}
              >
                Open existing entry
              </button>
            </div>
          )}
          {error && <p role="alert">{error}</p>}
          <button
            disabled={pending}
            className="min-h-11 rounded-full bg-fuchsia-500 px-6 font-semibold text-zinc-950 focus-ring"
          >
            {pending ? "Adding…" : "Add to library"}
          </button>
        </form>
      )}
    </main>
  );
}
