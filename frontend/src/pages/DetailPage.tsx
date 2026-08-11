import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  deleteEntry,
  getEntry,
  patchEntry,
  patchItem,
  refreshItem,
  replaceCover,
  type EntryStatus,
} from "@/api/library";
import { createShelf, getShelves } from "@/api/shelves";
import { ScorePicker } from "@/components/ScorePicker";

const statusLabels: Record<EntryStatus, string> = {
  unsorted: "Inbox",
  read: "Read",
  reading: "Reading",
  to_read: "To read",
  wishlist: "Wishlist",
  dropped: "Dropped",
};

export function DetailPage() {
  const entryId = Number(useParams().entryId);
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<
    "opinion" | "metadata" | "refresh" | "delete" | null
  >(null);
  const [error, setError] = useState("");
  const [newShelfName, setNewShelfName] = useState("");
  const [opinionScore, setOpinionScore] = useState<number | null>(null);
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

  // Sync opinionScore when opening the opinion dialog
  useEffect(() => {
    if (dialog === "opinion" && detail.data) setOpinionScore(detail.data.score);
  }, [dialog, detail.data]);

  // Restore focus to the dialog's first focusable element when it opens
  useEffect(() => {
    if (dialog) {
      const timer = window.setTimeout(() => {
        const el = document.querySelector<HTMLElement>(
          '[role="dialog"] [autofocus], [role="dialog"] input, [role="dialog"] select, [role="dialog"] button',
        );
        el?.focus();
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [dialog]);

  // Close dialog on Escape
  useEffect(() => {
    if (!dialog) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDialog(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dialog]);

  if (detail.isPending) return <p role="status">Loading book detail…</p>;
  if (!detail.data) return <p role="alert">Book detail could not be loaded</p>;
  const entry = detail.data;
  const item = entry.item;

  async function handleDelete() {
    try {
      await deleteEntry(entry.id);
      void cache.invalidateQueries({ queryKey: ["library"] });
      toast.success("Book removed from your library");
      navigate("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Entry could not be deleted");
    }
  }

  async function handleCreateShelf() {
    if (!newShelfName.trim()) return;
    try {
      await createShelf(newShelfName.trim());
      setNewShelfName("");
      void cache.invalidateQueries({ queryKey: ["shelves"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Shelf could not be created");
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <button className="focus-ring" onClick={() => navigate("/")}>
        ← Library
      </button>
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
              className="aspect-[2/3] rounded-xl bg-zinc-800"
              aria-label="No cover"
            />
          )}
          <label className="mt-3 block text-sm">
            Replace cover
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) update.mutate(() => replaceCover(item.id, file));
              }}
            />
          </label>
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
            <p className="text-lg text-zinc-400">{item.subtitle}</p>
          )}
          <p className="mt-2 text-zinc-300">
            {item.sort_author ?? "Unknown author"}
          </p>
          <p className="text-sm text-zinc-500">
            Edition year: {item.year ?? "unknown"}
            {item.metadata.original_year &&
            item.metadata.original_year !== item.year
              ? ` · Originally published: ${item.metadata.original_year}`
              : ""}
          </p>

          {/* Personal reading region */}
          <section
            className="mt-6 rounded-xl border border-zinc-800 p-5"
            aria-label="Your reading data"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wider text-fuchsia-400">
              Your reading data
            </h2>
            <dl className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs text-zinc-500">Status</dt>
                <dd>{statusLabels[entry.status]}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Score</dt>
                <dd>
                  {entry.score ?? "—"}
                  {entry.score_provisional && (
                    <span className="ml-1 text-xs text-amber-400">
                      (provisional)
                    </span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Started</dt>
                <dd>{entry.date_started ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Finished</dt>
                <dd>{entry.date_finished ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Rereads</dt>
                <dd>{entry.reread_count}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Shelves</dt>
                <dd>{entry.shelves.map((s) => s.name).join(", ") || "—"}</dd>
              </div>
            </dl>
            {entry.notes && (
              <div className="mt-4">
                <p className="text-xs text-zinc-500">Notes</p>
                <p className="mt-1 whitespace-pre-wrap text-zinc-300">
                  {entry.notes}
                </p>
              </div>
            )}
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                className="min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring"
                onClick={() => setDialog("opinion")}
              >
                Edit opinion
              </button>
              <button
                className="min-h-11 rounded-full border border-red-800 px-5 text-red-300 focus-ring"
                onClick={() => setDialog("delete")}
              >
                Delete entry
              </button>
            </div>
          </section>

          {/* Edition facts region */}
          <section
            className="mt-6 rounded-xl border border-zinc-800 p-5"
            aria-label="Edition facts"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wider text-fuchsia-400">
              Edition facts
            </h2>
            <dl className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs text-zinc-500">Publisher</dt>
                <dd>{item.metadata.publisher || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Language</dt>
                <dd>{item.metadata.language || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Pages</dt>
                <dd>{item.metadata.page_count ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Series</dt>
                <dd>{item.metadata.series || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Identifiers</dt>
                <dd>
                  {Object.entries(item.identifiers).map(([k, v]) => (
                    <span key={k} className="block text-sm">
                      {k}: {v}
                    </span>
                  ))}
                  {!Object.keys(item.identifiers).length && "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Sources</dt>
                <dd>
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
                </dd>
              </div>
            </dl>
            {item.metadata.subjects && item.metadata.subjects.length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-zinc-500">Subjects</p>
                <p className="mt-1 text-zinc-300">
                  {item.metadata.subjects.join(", ")}
                </p>
              </div>
            )}
            {item.metadata.description && (
              <div className="mt-4">
                <p className="text-xs text-zinc-500">Description</p>
                <p className="mt-1 whitespace-pre-wrap text-zinc-300">
                  {item.metadata.description}
                </p>
              </div>
            )}
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                className="min-h-11 rounded-full border border-zinc-700 px-5 focus-ring"
                onClick={() => setDialog("metadata")}
              >
                Edit book metadata
              </button>
              <button
                className="min-h-11 rounded-full border border-zinc-700 px-5 focus-ring"
                onClick={() => setDialog("refresh")}
              >
                Refresh from provider
              </button>
            </div>
          </section>
        </section>
      </div>

      {/* Opinion dialog */}
      {dialog === "opinion" && (
        <form
          role="dialog"
          aria-label="Edit opinion"
          aria-modal="true"
          className="dialog"
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            update.mutate(() =>
              patchEntry(entry.id, {
                status: String(data.get("status")) as EntryStatus,
                score: opinionScore,
                notes: String(data.get("notes") ?? ""),
                date_started: String(data.get("date_started") ?? "") || null,
                date_finished: String(data.get("date_finished") ?? "") || null,
                reread_count: Number(data.get("reread_count") ?? 0),
                shelf_ids: data.getAll("shelf_ids").map(Number),
              }),
            );
            setDialog(null);
          }}
        >
          <h2>Edit your opinion</h2>
          <label>
            Status
            <select name="status" defaultValue={entry.status} className="field">
              <option value="read">Read</option>
              <option value="reading">Reading</option>
              <option value="to_read">To read</option>
              <option value="wishlist">Wishlist</option>
              <option value="dropped">Dropped</option>
              <option value="unsorted">Inbox</option>
            </select>
          </label>
          <div>
            <span className="mb-1 block text-sm">Score</span>
            <ScorePicker
              value={opinionScore}
              provisional={entry.score_provisional}
              onChange={setOpinionScore}
            />
          </div>
          <label>
            Notes
            <textarea
              name="notes"
              defaultValue={entry.notes ?? ""}
              className="field"
            />
          </label>
          <label>
            Started
            <input
              name="date_started"
              type="date"
              defaultValue={entry.date_started ?? ""}
              className="field"
            />
          </label>
          <label>
            Finished
            <input
              name="date_finished"
              type="date"
              defaultValue={entry.date_finished ?? ""}
              className="field"
            />
          </label>
          <label>
            Reread count
            <input
              name="reread_count"
              type="number"
              min="0"
              defaultValue={entry.reread_count}
              className="field"
            />
          </label>
          {shelves.data && (
            <fieldset>
              <legend>Shelves</legend>
              {shelves.data.map((shelf) => (
                <label key={shelf.id} className="block">
                  <input
                    name="shelf_ids"
                    type="checkbox"
                    value={shelf.id}
                    defaultChecked={entry.shelves.some(
                      (value) => value.id === shelf.id,
                    )}
                  />{" "}
                  {shelf.name}
                </label>
              ))}
            </fieldset>
          )}
          {/* Inline shelf creation */}
          <div className="flex gap-2">
            <input
              className="field flex-1"
              placeholder="New shelf name"
              value={newShelfName}
              onChange={(e) => setNewShelfName(e.target.value)}
            />
            <button
              type="button"
              className="min-h-11 rounded-full border border-zinc-700 px-4 focus-ring"
              onClick={() => void handleCreateShelf()}
            >
              Create shelf
            </button>
          </div>
          <button className="min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring">
            Save opinion
          </button>
          <button type="button" onClick={() => setDialog(null)}>
            Cancel
          </button>
        </form>
      )}

      {/* Metadata dialog */}
      {dialog === "metadata" && (
        <form
          role="dialog"
          aria-label="Edit book metadata"
          aria-modal="true"
          className="dialog"
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            update.mutate(() =>
              patchItem(item.id, {
                title: String(data.get("title")),
                subtitle: String(data.get("subtitle") ?? "") || null,
                year: data.get("year") ? Number(data.get("year")) : null,
                metadata: {
                  ...item.metadata,
                  authors: String(data.get("authors") ?? "")
                    .split(",")
                    .map((v) => v.trim())
                    .filter(Boolean),
                  publisher: String(data.get("publisher") ?? ""),
                  language: String(data.get("language") ?? ""),
                  page_count: data.get("page_count")
                    ? Number(data.get("page_count"))
                    : null,
                  description: String(data.get("description") ?? "") || null,
                  subjects: String(data.get("subjects") ?? "")
                    .split(",")
                    .map((v) => v.trim())
                    .filter(Boolean),
                  series: String(data.get("series") ?? "") || null,
                  original_year: data.get("original_year")
                    ? Number(data.get("original_year"))
                    : null,
                },
              }),
            );
            setDialog(null);
          }}
        >
          <h2>Edit shared book metadata</h2>
          <p>Your score, status, dates, notes, and shelves are separate.</p>
          <label>
            Title
            <input
              autoFocus
              name="title"
              defaultValue={item.title}
              className="field"
            />
          </label>
          <label>
            Subtitle
            <input
              name="subtitle"
              defaultValue={item.subtitle ?? ""}
              className="field"
            />
          </label>
          <label>
            Year
            <input
              name="year"
              type="number"
              defaultValue={item.year ?? ""}
              className="field"
            />
          </label>
          <label>
            Authors
            <input
              name="authors"
              defaultValue={
                Array.isArray(item.metadata.authors)
                  ? item.metadata.authors.join(", ")
                  : ""
              }
              className="field"
            />
          </label>
          <label>
            Publisher
            <input
              name="publisher"
              defaultValue={String(item.metadata.publisher ?? "")}
              className="field"
            />
          </label>
          <label>
            Language
            <input
              name="language"
              defaultValue={String(item.metadata.language ?? "")}
              className="field"
            />
          </label>
          <label>
            Page count
            <input
              name="page_count"
              type="number"
              min="1"
              defaultValue={item.metadata.page_count ?? ""}
              className="field"
            />
          </label>
          <label>
            Description
            <textarea
              name="description"
              defaultValue={item.metadata.description ?? ""}
              className="field"
            />
          </label>
          <label>
            Subjects, comma separated
            <input
              name="subjects"
              defaultValue={(item.metadata.subjects ?? []).join(", ")}
              className="field"
            />
          </label>
          <label>
            Series
            <input
              name="series"
              defaultValue={item.metadata.series ?? ""}
              className="field"
            />
          </label>
          <label>
            Original publication year
            <input
              name="original_year"
              type="number"
              defaultValue={item.metadata.original_year ?? ""}
              className="field"
            />
          </label>
          <button className="min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring">
            Save metadata
          </button>
          <button type="button" onClick={() => setDialog(null)}>
            Cancel
          </button>
        </form>
      )}

      {/* Refresh dialog */}
      {dialog === "refresh" && (
        <div
          role="dialog"
          aria-label="Confirm metadata refresh"
          aria-modal="true"
          className="dialog"
        >
          <h2>Overwrite cached metadata?</h2>
          <p>
            Provider-managed fields will be replaced. Opinion data is preserved.
          </p>
          <button
            autoFocus
            className="min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring"
            onClick={() => {
              update.mutate(() => refreshItem(item.id));
              setDialog(null);
            }}
          >
            Confirm refresh
          </button>
          <button type="button" onClick={() => setDialog(null)}>
            Cancel
          </button>
        </div>
      )}

      {/* Delete dialog */}
      {dialog === "delete" && (
        <div
          role="dialog"
          aria-label="Confirm entry deletion"
          aria-modal="true"
          className="dialog"
        >
          <h2>Remove this book from your library?</h2>
          <p>
            Your score, status, notes, and shelf assignments will be deleted.
            The book metadata and cover remain cached so re-adding is instant.
          </p>
          <button
            autoFocus
            className="min-h-11 rounded-full bg-red-600 px-5 font-semibold text-zinc-950 focus-ring"
            onClick={() => void handleDelete()}
          >
            Delete entry
          </button>
          <button type="button" onClick={() => setDialog(null)}>
            Cancel
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-4 text-red-300">
          {error}
        </p>
      )}
    </main>
  );
}
