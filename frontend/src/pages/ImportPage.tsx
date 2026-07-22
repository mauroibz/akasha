import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  commitGoodreads,
  previewGoodreads,
  type ImportPreview,
  type ImportResult,
} from "@/api/imports";

export function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [choices, setChoices] = useState<Record<number, number | "new">>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const resultRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (preview) heading.current?.focus();
  }, [preview]);
  useEffect(() => {
    if (result) resultRef.current?.focus();
  }, [result]);

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
        Goodreads CSV is previewed locally before anything enters your library.
        Metadata enrichment and undo are not part of this step.
      </p>
      {!preview && (
        <form
          className="mt-8 space-y-5 rounded-2xl bg-zinc-900 p-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (!file) return;
            setPending(true);
            setError("");
            void previewGoodreads(file)
              .then(setPreview)
              .catch((reason: Error) => setError(reason.message))
              .finally(() => setPending(false));
          }}
        >
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
          <button
            className="focus-ring rounded-full bg-fuchsia-600 px-5 py-3"
            disabled={pending || !file}
          >
            {pending ? "Reading file…" : "Preview import"}
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
                  {record.score ? ` · provisional score ${record.score}` : ""}
                  {record.suggested_status
                    ? ` · suggested ${record.suggested_status}`
                    : ""}
                </p>
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
              void commitGoodreads(
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
    </main>
  );
}
