import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  commitGoodreads,
  commitCalibre,
  previewCalibre,
  previewGoodreads,
  undoBatch,
  type ImportPreview,
  type ImportResult,
  type UndoResult,
} from "@/api/imports";

export function ImportPage() {
  const [source, setSource] = useState<"goodreads" | "calibre">("goodreads");
  const [file, setFile] = useState<File | null>(null);
  const [libraryPath, setLibraryPath] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [choices, setChoices] = useState<Record<number, number | "new">>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [undoResult, setUndoResult] = useState<UndoResult | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [undoPending, setUndoPending] = useState(false);
  const [confirmUndo, setConfirmUndo] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const resultRef = useRef<HTMLParagraphElement>(null);
  const undoRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (preview) heading.current?.focus();
  }, [preview]);
  useEffect(() => {
    if (result) resultRef.current?.focus();
  }, [result]);
  useEffect(() => {
    if (undoResult) undoRef.current?.focus();
  }, [undoResult]);

  const unresolved =
    preview?.records.filter(
      (record) =>
        record.planned_action === "ambiguous" && !choices[record.record_id],
    ).length ?? 0;
  const ready =
    (preview?.summary.ready ?? 0) + (preview?.summary.ambiguous ?? 0);

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <Link className="focus-ring" to="/">
        ← Library
      </Link>
      <h1 className="mt-6 text-4xl font-semibold">Import books</h1>
      <p className="mt-2 text-zinc-400">
        Preview a source before anything enters your library. Existing values
        are preserved when a re-sync only supplies missing metadata.
      </p>
      {!preview && (
        <div
          className="mt-7 flex gap-2"
          role="tablist"
          aria-label="Import source"
        >
          {(["goodreads", "calibre"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={source === value}
              className={`focus-ring rounded-full px-5 py-2 capitalize ${source === value ? "bg-fuchsia-600" : "bg-zinc-800"}`}
              onClick={() => {
                setSource(value);
                setError("");
              }}
            >
              {value}
            </button>
          ))}
        </div>
      )}
      {!preview && (
        <form
          className="mt-8 space-y-5 rounded-2xl bg-zinc-900 p-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (source === "goodreads" && !file) return;
            if (source === "calibre" && !libraryPath.trim()) return;
            setPending(true);
            setError("");
            const request =
              source === "goodreads"
                ? previewGoodreads(file as File)
                : previewCalibre(libraryPath.trim());
            void request
              .then(setPreview)
              .catch((reason: Error) => setError(reason.message))
              .finally(() => setPending(false));
          }}
        >
          {source === "goodreads" ? (
            <label className="block">
              Goodreads CSV
              <input
                autoFocus
                className="field"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
          ) : (
            <>
              <p className="rounded-xl bg-zinc-800 p-4 text-sm text-zinc-300">
                Akasha opens this library read-only inside the configured
                Calibre mount. Enter a relative folder only; absolute paths and
                parent traversal are rejected. Covers are copied during preview
                so the source is never needed during commit.
              </p>
              <label className="block">
                Calibre library path
                <input
                  autoFocus
                  className="field"
                  value={libraryPath}
                  placeholder="Library"
                  onChange={(event) => setLibraryPath(event.target.value)}
                />
              </label>
            </>
          )}
          <button
            className="focus-ring rounded-full bg-fuchsia-600 px-5 py-3"
            disabled={
              pending || (source === "goodreads" ? !file : !libraryPath.trim())
            }
          >
            {pending
              ? "Reading source…"
              : source === "calibre"
                ? "Preview Calibre library"
                : "Preview import"}
          </button>
        </form>
      )}
      {error && (
        <p className="mt-4 text-red-300" role="alert">
          {error}
        </p>
      )}
      {preview && !result && (
        <section className="mt-8">
          <h2 ref={heading} tabIndex={-1} className="text-2xl font-semibold">
            Preview: {preview.summary.total} rows
          </h2>
          <p className="mt-2" role="status">
            {preview.summary.ready} ready · {preview.summary.ambiguous} need a
            choice · {preview.summary.errors} have errors
          </p>
          <div className="mt-5 space-y-3">
            {preview.records.map((record) => (
              <article
                key={record.record_id}
                className="rounded-2xl bg-zinc-900 p-4"
              >
                <h3 className="font-semibold">
                  {record.title || `Row ${record.row_number}`}
                </h3>
                <p className="text-sm text-zinc-400">
                  {record.authors.join(", ") || "Author missing"}
                  {record.score
                    ? record.score_provisional
                      ? ` · provisional score ${record.score}`
                      : ` · rating ${record.score}`
                    : ""}
                  {record.suggested_status
                    ? ` · suggested ${record.suggested_status}`
                    : ""}
                </p>
                {record.cover_staged && (
                  <p className="text-sm text-emerald-300">Local cover staged</p>
                )}
                {record.errors.map((row, index) => (
                  <p
                    key={`${row.field}-${index}`}
                    className="text-sm text-red-300"
                  >
                    {row.field}: {row.code}
                  </p>
                ))}
                {record.planned_action === "ambiguous" && (
                  <label className="mt-3 block">
                    Choice for {record.title}
                    <select
                      required
                      className="field"
                      value={choices[record.record_id] ?? ""}
                      onChange={(event) =>
                        setChoices((old) => ({
                          ...old,
                          [record.record_id]:
                            event.target.value === "new"
                              ? "new"
                              : Number(event.target.value),
                        }))
                      }
                    >
                      <option value="">Choose…</option>
                      {record.candidates.map((id) => (
                        <option key={id} value={id}>
                          Use existing item {id}
                        </option>
                      ))}
                      <option value="new">Create a separate edition</option>
                    </select>
                  </label>
                )}
              </article>
            ))}
          </div>
          <button
            className="mt-6 rounded-full bg-fuchsia-600 px-5 py-3 focus-ring disabled:opacity-50"
            disabled={pending || unresolved > 0 || ready === 0}
            onClick={() => {
              setPending(true);
              setError("");
              const commit =
                source === "calibre" ? commitCalibre : commitGoodreads;
              void commit(
                preview.batch_id,
                Object.entries(choices).map(([recordId, value]) => ({
                  record_id: Number(recordId),
                  item_id: value === "new" ? null : value,
                })),
              )
                .then(setResult)
                .catch((reason: Error) => setError(reason.message))
                .finally(() => setPending(false));
            }}
          >
            {pending
              ? "Importing…"
              : `Import ${ready} ready ${ready === 1 ? "row" : "rows"}`}
          </button>
        </section>
      )}
      {result && (
        <p ref={resultRef} tabIndex={-1} className="mt-8 text-xl" role="status">
          Import complete: {result.created_entries}{" "}
          {result.created_entries === 1 ? "book" : "books"} added;{" "}
          {result.unchanged_entries} already present.
        </p>
      )}
      {result && !undoResult && (
        <div className="mt-5 rounded-2xl bg-zinc-900 p-4">
          <p className="text-sm text-zinc-400">
            You can undo this import for 24 hours after commit. The undo
            reverses only fields that still match the imported values — your
            later edits are preserved.
          </p>
          {!confirmUndo ? (
            <button
              className="focus-ring mt-3 rounded-full bg-red-900 px-5 py-2 text-sm"
              onClick={() => setConfirmUndo(true)}
            >
              Undo this import
            </button>
          ) : (
            <div className="mt-3 flex gap-2">
              <button
                className="focus-ring rounded-full bg-red-700 px-5 py-2 text-sm disabled:opacity-50"
                disabled={undoPending}
                onClick={() => {
                  setUndoPending(true);
                  setError("");
                  void undoBatch(result.batch_id)
                    .then((res) => {
                      setUndoResult(res);
                      setConfirmUndo(false);
                    })
                    .catch((reason: Error) => setError(reason.message))
                    .finally(() => setUndoPending(false));
                }}
              >
                {undoPending ? "Undoing…" : "Confirm undo"}
              </button>
              <button
                className="focus-ring rounded-full bg-zinc-800 px-5 py-2 text-sm"
                onClick={() => setConfirmUndo(false)}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}
      {undoResult && (
        <div
          ref={undoRef}
          tabIndex={-1}
          className="mt-5 rounded-2xl bg-zinc-900 p-4"
          role="status"
        >
          <h2 className="text-lg font-semibold">Import undone</h2>
          <p className="mt-1 text-sm text-zinc-300">
            {undoResult.reverted}{" "}
            {undoResult.reverted === 1 ? "change" : "changes"} reverted
            {undoResult.retained > 0 && ` · ${undoResult.retained} retained (edited after import)`}
          </p>
          <Link className="focus-ring mt-3 inline-block text-fuchsia-400" to="/">
            ← Back to library
          </Link>
        </div>
      )}
    </main>
  );
}
