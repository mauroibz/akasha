import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
  type ImportInputSpec,
  ImportRequestError,
  previewImport,
  type ImporterDefinition,
  undoBatch,
  type ImportPreview,
  type ImportResult,
  type UndoResult,
} from "@/api/imports";
import type { BundleMember, CalibreBundle } from "@/features/import/bundle";
import { ConnectorGuide } from "@/features/import/ConnectorGuide";
import { DirectoryPicker } from "@/features/import/DirectoryPicker";
import { FolderPicker } from "@/features/import/FolderPicker";
import { SourceDropZone } from "@/features/import/SourceDropZone";
import { TriagePage } from "@/pages/TriagePage";

/** A refusal as the screen shows it: what happened, and what to do about it. */
interface ImportFailure {
  readonly message: string;
  readonly action: string | null;
}

function asFailure(reason: Error): ImportFailure {
  return {
    message: reason.message,
    action: reason instanceof ImportRequestError ? reason.action : null,
  };
}

/**
 * The tab that holds the inbox rather than an importer.
 *
 * Triage used to be a top-level destination, and it is empty unless an import
 * has just landed rows `unsorted` — so most visits met a dead page. It is not
 * an independent screen, it is the tail of this flow, and it lives here now
 * (DEC-079).
 */
export const TRIAGE_TAB = "triage";

/** The importer used last, so a second Calibre re-sync opens where you left. */
export const importSourcePreferenceKey = "akasha.import.source";

function rememberedSource(): string {
  try {
    return localStorage.getItem(importSourcePreferenceKey) ?? "";
  } catch {
    return "";
  }
}

export function ImportPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [importers, setImporters] = useState<ImporterDefinition[]>([]);
  const [fallbackSource, setFallbackSource] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [libraryPath, setLibraryPath] = useState("");
  const [bundle, setBundle] = useState<CalibreBundle | null>(null);
  const [showAlternate, setShowAlternate] = useState(false);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [choices, setChoices] = useState<Record<number, number | "new">>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [undoResult, setUndoResult] = useState<UndoResult | null>(null);
  const [error, setError] = useState<ImportFailure | null>(null);
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
        // What the URL does not name: the connector used last, else the first
        // one declared. Same order the library's domain tab follows (DEC-062) —
        // a link stays shareable, and a habit costs no click.
        const remembered = rememberedSource();
        setFallbackSource(
          available.some((importer) => importer.id === remembered)
            ? remembered
            : (available[0]?.id ?? ""),
        );
      })
      .catch((reason: Error) => setError(asFailure(reason)));
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

  // The URL is the tab, so the post-commit "Open Triage" link and a pasted
  // address both land where they say they do; local state only covers the
  // moment before the registry has arrived.
  const asked = searchParams.get("tab") ?? "";
  const source =
    asked === TRIAGE_TAB || importers.some((importer) => importer.id === asked)
      ? asked
      : fallbackSource;
  const triageActive = source === TRIAGE_TAB;

  useEffect(() => setError(null), [source]);

  // A staged source, its preview and its undo window belong to the connector
  // that produced them. Moving to another connector starts clean; moving to
  // Triage and back does not, because Triage is not a connector — and the undo
  // window is only reachable from the result panel it would otherwise discard.
  // The walkthrough found this: after a Goodreads commit, the Calibre tab
  // showed the Goodreads result and no Calibre form at all.
  const belongsTo = useRef("");
  useEffect(() => {
    if (!source || source === TRIAGE_TAB || belongsTo.current === source)
      return;
    belongsTo.current = source;
    setFile(null);
    setLibraryPath("");
    setBundle(null);
    setShowAlternate(false);
    setPreview(null);
    setResult(null);
    setUndoResult(null);
    setChoices({});
    setConfirmUndo(false);
  }, [source]);

  const selectTab = (value: string) => {
    if (value !== TRIAGE_TAB) {
      try {
        localStorage.setItem(importSourcePreferenceKey, value);
      } catch {
        // Storage refused: the memory is lost, the screen is not.
      }
    }
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("tab", value);
        return next;
      },
      { replace: true },
    );
  };

  const unresolved =
    preview?.records.filter(
      (record) =>
        record.planned_action === "ambiguous" && !choices[record.record_id],
    ).length ?? 0;
  const ready =
    (preview?.summary.ready ?? 0) + (preview?.summary.ambiguous ?? 0);
  const activeImporter = importers.find((importer) => importer.id === source);

  /**
   * Which of a connector's inputs the reader actually filled in, if any.
   *
   * A connector may offer two (DEC-081), so "is this ready to preview" is a
   * question about the whole tab rather than about one field. The folder wins
   * when both are filled, because it is the one the tab leads with.
   */
  const readyInput = (
    importer: ImporterDefinition | undefined,
  ): {
    spec: ImportInputSpec;
    source: File | string | BundleMember[];
  } | null => {
    if (!importer) return null;
    for (const spec of [importer.input, importer.input.alternate]) {
      if (!spec) continue;
      if (
        spec.kind === "directory" &&
        bundle?.database &&
        bundle.members.length
      )
        return { spec, source: bundle.members };
      if (spec.kind === "upload" && file) return { spec, source: file };
      if (spec.kind === "path" && libraryPath.trim())
        return { spec, source: libraryPath.trim() };
    }
    return null;
  };

  const renderInput = (
    importer: ImporterDefinition,
    spec: ImportInputSpec,
    suffix: string,
  ) => {
    const inputId = `${importer.id}-source${suffix}`;
    if (spec.kind === "directory")
      return (
        <DirectoryPicker
          spec={spec}
          importerLabel={importer.label}
          inputId={inputId}
          bundle={bundle}
          onBundle={setBundle}
        />
      );
    if (spec.kind === "upload")
      return (
        <SourceDropZone
          importer={importer}
          inputId={inputId}
          file={file}
          onFile={setFile}
        />
      );
    return (
      <div className="space-y-3">
        {spec.browsable && (
          <FolderPicker
            importerId={importer.id}
            importerLabel={importer.label}
            emptyState={spec.empty_state}
            selected={libraryPath}
            onSelect={setLibraryPath}
          />
        )}
        <div className="block">
          <Label htmlFor={inputId}>{spec.label}</Label>
          <Input
            id={inputId}
            className="mt-1 h-11"
            value={libraryPath}
            placeholder={spec.placeholder ?? undefined}
            onChange={(event) => setLibraryPath(event.target.value)}
          />
        </div>
      </div>
    );
  };

  const tabStrip = (
    <TabsList aria-label="Import source">
      {importers.map((importer) => (
        <TabsTrigger key={importer.id} value={importer.id}>
          {importer.label}
        </TabsTrigger>
      ))}
      {/* Not an importer, and deliberately last: the inbox is where a finished
          import ends up, not another place to start one. */}
      <TabsTrigger value={TRIAGE_TAB}>Triage</TabsTrigger>
    </TabsList>
  );

  if (triageActive)
    return (
      <Tabs value={source} onValueChange={selectTab}>
        {/* No "← Library" here: the triage surface carries its own, and the
            walkthrough showed the two side by side, announcing one destination
            twice. */}
        <div className="mx-auto max-w-7xl px-5 pt-7 sm:px-8">{tabStrip}</div>
        {/* The inbox is the surface it has always been: this renders the
            component, it does not restate it. Its own `<main>` is the only
            landmark on screen, because the import side is not mounted beside
            it. */}
        <TabsContent value={TRIAGE_TAB} className="mt-0">
          <TriagePage />
        </TabsContent>
      </Tabs>
    );

  return (
    <Tabs value={source} onValueChange={selectTab} asChild>
      <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
        <Link className="focus-ring" to="/">
          ← Library
        </Link>
        <h1 className="mt-6 text-4xl font-semibold">Import</h1>
        <p className="mt-2 text-muted-foreground">
          Preview a source before anything enters your library. Existing values
          are preserved when a re-sync only supplies missing metadata.
        </p>
        {importers.length > 0 && <div className="mt-7">{tabStrip}</div>}
        {!preview && importers.length > 0 && (
          <>
            {/* The panel each trigger names has to exist. Without it Radix still
              writes `aria-controls` pointing at nothing, which axe reports as a
              critical invalid attribute value and which leaves a screen reader
              unable to reach the fields the tab just switched to (DEC-038). */}
            <form
              className="mt-8 space-y-5 rounded-2xl bg-surface p-5"
              onSubmit={(event) => {
                event.preventDefault();
                const submission = readyInput(activeImporter);
                if (!submission) return;
                setPending(true);
                setError(null);
                void previewImport(
                  activeImporter as ImporterDefinition,
                  submission.spec,
                  submission.source,
                )
                  .then(setPreview)
                  .catch((reason: Error) => setError(asFailure(reason)))
                  .finally(() => setPending(false));
              }}
            >
              {importers.map((importer) => (
                <TabsContent
                  key={importer.id}
                  value={importer.id}
                  className="mt-0 space-y-5"
                >
                  <ConnectorGuide importer={importer} />
                  {renderInput(importer, importer.input, "")}
                  {/* The second way in, beneath the first. One deep by contract,
                      so this never recurses further (DEC-081). */}
                  {importer.input.alternate && (
                    // A controlled disclosure rather than `<details>`: this is the
                    // second way in, so it needs an explicit expanded state that a
                    // screen reader announces and a test can drive.
                    <div className="rounded-2xl border border-border px-4 py-3">
                      <Button
                        type="button"
                        variant="ghost"
                        aria-expanded={showAlternate}
                        aria-controls={`${importer.id}-alternate`}
                        className="h-8 w-full justify-start rounded-lg px-2 text-sm font-normal text-muted-foreground"
                        onClick={() => setShowAlternate((open) => !open)}
                      >
                        {importer.input.alternate.help ??
                          `Or use a ${importer.label} library the server can already see`}
                      </Button>
                      {showAlternate && (
                        <div id={`${importer.id}-alternate`} className="mt-4">
                          {renderInput(
                            importer,
                            importer.input.alternate,
                            "-alt",
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </TabsContent>
              ))}
              <Button
                className="rounded-full px-5"
                disabled={pending || readyInput(activeImporter) === null}
              >
                {pending
                  ? "Reading source…"
                  : activeImporter && activeImporter.input.kind !== "upload"
                    ? `Preview ${activeImporter.label} library`
                    : "Preview import"}
              </Button>
            </form>
          </>
        )}
        {error && (
          // The action is the connector's, not this screen's: only Calibre knows
          // that a locked database means "close Calibre and try again" (DEC-080).
          <div className="mt-4 rounded-xl bg-destructive/10 p-4" role="alert">
            <p className="text-destructive">{error.message}</p>
            {error.action && (
              <p className="mt-1 text-sm text-foreground">{error.action}</p>
            )}
          </div>
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
                setError(null);
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
                  .catch((reason: Error) => setError(asFailure(reason)))
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
                <Link
                  className="focus-ring text-primary"
                  to={`/import?tab=${TRIAGE_TAB}`}
                >
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
                    setError(null);
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
                      .catch((reason: Error) => setError(asFailure(reason)))
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
    </Tabs>
  );
}
