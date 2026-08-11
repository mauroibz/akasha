import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
      <p className="mt-2 text-muted-foreground">
        Preview a source before anything enters your library. Existing values
        are preserved when a re-sync only supplies missing metadata.
      </p>
      {!preview && (
        <Tabs
          className="mt-7"
          value={source}
          onValueChange={(value) => {
            setSource(value as "goodreads" | "calibre");
            setError("");
          }}
        >
          <TabsList aria-label="Import source">
            <TabsTrigger value="goodreads" className="capitalize">
              goodreads
            </TabsTrigger>
            <TabsTrigger value="calibre" className="capitalize">
              calibre
            </TabsTrigger>
          </TabsList>
        </Tabs>
      )}
      {!preview && (
        <form
          className="mt-8 space-y-5 rounded-2xl bg-surface p-5"
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
            <div className="block">
              <Label htmlFor="goodreads-csv">Goodreads CSV</Label>
              <Input
                id="goodreads-csv"
                autoFocus
                className="mt-1 h-11 py-2"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </div>
          ) : (
            <>
              <p className="rounded-xl bg-surface-raised p-4 text-sm text-foreground">
                Akasha opens this library read-only inside the configured
                Calibre mount. Enter a relative folder only; absolute paths and
                parent traversal are rejected. Covers are copied during preview
                so the source is never needed during commit.
              </p>
              <div className="block">
                <Label htmlFor="calibre-path">Calibre library path</Label>
                <Input
                  id="calibre-path"
                  autoFocus
                  className="mt-1 h-11"
                  value={libraryPath}
                  placeholder="Library"
                  onChange={(event) => setLibraryPath(event.target.value)}
                />
              </div>
            </>
          )}
          <Button
            className="rounded-full px-5"
            disabled={
              pending || (source === "goodreads" ? !file : !libraryPath.trim())
            }
          >
            {pending
              ? "Reading source…"
              : source === "calibre"
                ? "Preview Calibre library"
                : "Preview import"}
          </Button>
        </form>
      )}
      {error && (
        <p className="mt-4 text-destructive" role="alert">
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
                className="rounded-2xl bg-surface p-4"
              >
                <h3 className="font-semibold">
                  {record.title || `Row ${record.row_number}`}
                </h3>
                <p className="text-sm text-muted-foreground">
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
                  <p className="text-sm text-score-top">Local cover staged</p>
                )}
                {record.errors.map((row, index) => (
                  <p
                    key={`${row.field}-${index}`}
                    className="text-sm text-destructive"
                  >
                    {row.field}: {row.code}
                  </p>
                ))}
                {record.planned_action === "ambiguous" && (
                  <div className="mt-3 block">
                    <Label htmlFor={`choice-${record.record_id}`}>
                      Choice for {record.title}
                    </Label>
                    <Select
                      value={String(choices[record.record_id] ?? "")}
                      onValueChange={(value) =>
                        setChoices((old) => ({
                          ...old,
                          [record.record_id]:
                            value === "new" ? "new" : Number(value),
                        }))
                      }
                    >
                      <SelectTrigger
                        id={`choice-${record.record_id}`}
                        aria-label={`Choice for ${record.title}`}
                        className="mt-1 h-11"
                      >
                        <SelectValue placeholder="Choose…" />
                      </SelectTrigger>
                      <SelectContent>
                        {record.candidates.map((id) => (
                          <SelectItem key={id} value={String(id)}>
                            Use existing item {id}
                          </SelectItem>
                        ))}
                        <SelectItem value="new">
                          Create a separate edition
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </article>
            ))}
          </div>
          <Button
            className="mt-6 rounded-full px-5"
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
                .then((committed) => {
                  setResult(committed);
                  toast.success(
                    `Import complete: ${committed.created_entries} ${
                      committed.created_entries === 1 ? "book" : "books"
                    } added`,
                    { description: "Undo stays available for 24 hours." },
                  );
                })
                .catch((reason: Error) => setError(reason.message))
                .finally(() => setPending(false));
            }}
          >
            {pending
              ? "Importing…"
              : `Import ${ready} ready ${ready === 1 ? "row" : "rows"}`}
          </Button>
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
        <div className="mt-5 rounded-2xl bg-surface p-4">
          <p className="text-sm text-muted-foreground">
            You can undo this import for 24 hours after commit. The undo
            reverses only fields that still match the imported values — your
            later edits are preserved.
          </p>
          {!confirmUndo ? (
            <Button
              variant="outline"
              className="mt-3 rounded-full border-destructive/60 text-sm text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setConfirmUndo(true)}
            >
              Undo this import
            </Button>
          ) : (
            <div className="mt-3 flex gap-2">
              <Button
                variant="destructive"
                className="rounded-full text-sm"
                disabled={undoPending}
                onClick={() => {
                  setUndoPending(true);
                  setError("");
                  void undoBatch(result.batch_id)
                    .then((res) => {
                      setUndoResult(res);
                      setConfirmUndo(false);
                      toast.success(
                        `Import undone: ${res.reverted} ${
                          res.reverted === 1 ? "change" : "changes"
                        } reverted`,
                      );
                    })
                    .catch((reason: Error) => setError(reason.message))
                    .finally(() => setUndoPending(false));
                }}
              >
                {undoPending ? "Undoing…" : "Confirm undo"}
              </Button>
              <Button
                variant="secondary"
                className="rounded-full text-sm"
                onClick={() => setConfirmUndo(false)}
              >
                Cancel
              </Button>
            </div>
          )}
        </div>
      )}
      {undoResult && (
        <div
          ref={undoRef}
          tabIndex={-1}
          className="mt-5 rounded-2xl bg-surface p-4"
          role="status"
        >
          <h2 className="text-lg font-semibold">Import undone</h2>
          <p className="mt-1 text-sm text-foreground">
            {undoResult.reverted}{" "}
            {undoResult.reverted === 1 ? "change" : "changes"} reverted
            {undoResult.retained > 0 &&
              ` · ${undoResult.retained} retained (edited after import)`}
          </p>
          <Link className="focus-ring mt-3 inline-block text-primary" to="/">
            ← Back to library
          </Link>
        </div>
      )}
    </main>
  );
}
