import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  getEntry,
  patchEntry,
  patchItem,
  refreshItem,
  replaceCover,
  type EntryStatus,
} from "@/api/library";
import { getShelves } from "@/api/add";

export function DetailPage() {
  const entryId = Number(useParams().entryId);
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<
    "opinion" | "metadata" | "refresh" | null
  >(null);
  const [error, setError] = useState("");
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
  if (detail.isPending) return <p role="status">Loading book detail…</p>;
  if (!detail.data) return <p role="alert">Book detail could not be loaded</p>;
  const entry = detail.data;
  const item = entry.item;
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <button className="focus-ring" onClick={() => navigate("/")}>
        ← Library
      </button>
      <div className="mt-8 grid gap-8 md:grid-cols-[240px_1fr]">
        <aside>
          {item.cover_path ? (
            <img
              className="aspect-[2/3] w-full rounded-xl object-cover"
              src={`/${item.cover_path}`}
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
          <h1 className="text-4xl font-semibold">{item.title}</h1>
          <p className="text-zinc-400">{item.subtitle}</p>
          <p>
            {item.sort_author} · {item.year}
          </p>
          <p className="mt-5">{String(item.metadata.description ?? "")}</p>
          <dl className="mt-6 grid grid-cols-2 gap-4">
            <div>
              <dt>Status</dt>
              <dd>{entry.status}</dd>
            </div>
            <div>
              <dt>Score</dt>
              <dd>{entry.score ?? "—"}</dd>
            </div>
            <div>
              <dt>Notes</dt>
              <dd>{entry.notes ?? "—"}</dd>
            </div>
            <div>
              <dt>Shelves</dt>
              <dd>{entry.shelves.map((s) => s.name).join(", ") || "—"}</dd>
            </div>
          </dl>
          <div className="mt-6 flex flex-wrap gap-3">
            <button onClick={() => setDialog("opinion")}>Edit opinion</button>
            <button onClick={() => setDialog("metadata")}>
              Edit book metadata
            </button>
            <button onClick={() => setDialog("refresh")}>
              Refresh from provider
            </button>
          </div>
        </section>
      </div>
      {dialog === "opinion" && (
        <form
          role="dialog"
          aria-label="Edit opinion"
          className="dialog"
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            update.mutate(() =>
              patchEntry(entry.id, {
                status: String(data.get("status")) as EntryStatus,
                score: data.get("score") ? Number(data.get("score")) : null,
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
          <label>
            Score
            <input
              name="score"
              defaultValue={entry.score ?? ""}
              min="1"
              max="10"
              type="number"
              className="field"
            />
          </label>
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
          <button>Save opinion</button>
          <button type="button" onClick={() => setDialog(null)}>
            Cancel
          </button>
        </form>
      )}
      {dialog === "metadata" && (
        <form
          role="dialog"
          aria-label="Edit book metadata"
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
          <button>Save metadata</button>
          <button type="button" onClick={() => setDialog(null)}>
            Cancel
          </button>
        </form>
      )}
      {dialog === "refresh" && (
        <div
          role="dialog"
          aria-label="Confirm metadata refresh"
          className="dialog"
        >
          <h2>Overwrite cached metadata?</h2>
          <p>
            Provider-managed fields will be replaced. Opinion data is preserved.
          </p>
          <button
            onClick={() => {
              update.mutate(() => refreshItem(item.id));
              setDialog(null);
            }}
          >
            Confirm refresh
          </button>
          <button onClick={() => setDialog(null)}>Cancel</button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
