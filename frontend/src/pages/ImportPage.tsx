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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  commitImport,
  getImporters,
  previewImport,
  type ImporterDefinition,
  undoBatch,
  type ImportPreview,
  type ImportResult,
  type UndoResult,
} from "@/api/imports";

export function ImportPage() {
  const [importers, setImporters] = useState<ImporterDefinition[]>([]);
  const [source, setSource] = useState("");
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
  const resultRef = useRef<HTMLDivElement>(null);
  const undoRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void getImporters()
      .then((available) => {
        setImporters(available);
        setSource((current) => current || available[0]?.id || "");
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

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
  const activeImporter = importers.find((importer) => importer.id === source);

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <Link className="focus-ring" to="/">
        ← Library
      </Link>
      <h1 className="mt-6 text-4xl font-semibold">Import</h1>
      <p className="mt-2 text-muted-foreground">
        Preview a source before anything enters your library. Existing values
        are preserved when a re-sync only supplies missing metadata.
      </p>
      {!preview && importers.length > 0 && (
        <Tabs
          className="mt-7"
          value={source}
          onValueChange={(value) => {
            setSource(value);
            setError("");
          }}
        >
          <TabsList aria-label="Import source">
            {importers.map((importer) => (
              <TabsTrigger key={importer.id} value={importer.id}>
                {importer.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {/* The panel each trigger names has to exist. Without it Radix still
              writes `aria-controls` pointing at nothing, which axe reports as a
              critical invalid attribute value and which leaves a screen reader
              unable to reach the fields the tab just switched to (DEC-038). */}
          <form
            className="mt-8 space-y-5 rounded-2xl bg-surface p-5"
            onSubmit={(event) => {
              event.preventDefault();
              if (!activeImporter) return;
              if (activeImporter.input.kind === "upload" && !file) return;
              if (activeImporter.input.kind === "path" && !libraryPath.trim())
                return;
              setPending(true);
              setError("");
              void previewImport(
                activeImporter,
                activeImporter.input.kind === "upload"
                  ? (file as File)
                  : libraryPath.trim(),
              )
                .then(setPreview)
                .catch((reason: Error) => setError(reason.message))
                .finally(() => setPending(false));
            }}
          >
            {importers.map((importer) => {
              const inputId = `${importer.id}-source`;
              return (
                <TabsContent
                  key={importer.id}
                  value={importer.id}
                  className="mt-0 space-y-5"
                >
                  {importer.input.help && (
                    <p className="rounded-xl bg-surface-raised p-4 text-sm text-foreground">
                      {importer.input.help}
                    </p>
                  )}
                  <div className="block">
                    <Label htmlFor={inputId}>{importer.input.label}</Label>
                    {importer.input.kind === "upload" ? (
                      <Input
                        id={inputId}
                        autoFocus
                        className="mt-1 h-11 py-2"
                        type="file"
                        accept={importer.input.accept ?? undefined}
                        onChange={(event) =>
                          setFile(event.target.files?.[0] ?? null)
                        }
                      />
                    ) : (
                      <Input
                        id={inputId}
                        autoFocus
                        className="mt-1 h-11"
                        value={libraryPath}
                        placeholder={importer.input.placeholder ?? undefined}
                        onChange={(event) => setLibraryPath(event.target.value)}
                      />
                    )}
                  </div>
                </TabsContent>
              );
            })}
            <Button
              className="rounded-full px-5"
              disabled={
                pending ||
                !activeImporter ||
                (activeImporter.input.kind === "upload"
                  ? !file
                  : !libraryPath.trim())
              }
            >
              {pending
                ? "Reading source…"
                : activeImporter?.input.kind === "path"
                  ? `Preview ${activeImporter.label} library`
                  : "Preview import"}
            </Button>
          </form>
        </Tabs>
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
                  {record.creators.join(", ") || "Creator missing"}
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
              void commitImport(
                source,
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
                      committed.created_entries === 1 ? "entry" : "entries"
                    } added`,
                    {
                      description: committed.unsorted_entries
                        ? `${committed.unsorted_entries} waiting in Triage. Undo stays available for 24 hours.`
                        : "Undo stays available for 24 hours.",
                    },
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
        <div ref={resultRef} tabIndex={-1} className="mt-8" role="status">
          <p className="text-xl">
            Import complete: {result.created_entries}{" "}
            {result.created_entries === 1 ? "entry" : "entries"} added;{" "}
            {result.unchanged_entries} already present.
          </p>
          {/* Imported rows land `unsorted`, and the library's default view
              excludes `unsorted`, so a successful import used to look like a
              no-op: the count went up and the shelf stayed empty. Say where the
              rows went and offer the one click that gets there. The count is
              everything waiting, which can exceed what this batch added. */}
          {result.unsorted_entries > 0 && (
            <p className="mt-2 text-muted-foreground">
              {result.unsorted_entries}{" "}
              {result.unsorted_entries === 1 ? "entry is" : "entries are"}{" "}
              waiting in Triage. Your library hides unsorted entries until you
              sort them, so this is where the import went.{" "}
              <Link className="focus-ring text-primary" to="/triage">
                Open Triage →
              </Link>
            </p>
          )}
        </div>
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
