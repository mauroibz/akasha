import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { BackToLibrary } from "@/components/BackToLibrary";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
  getPreview,
  type ImportInputSpec,
  ImportRequestError,
  planImport,
  previewImport,
  previewImportWithOptions,
  type ImporterDefinition,
  type ImportPreview,
  type ImportResult,
  type UndoResult,
  undoBatch,
  uploadImportFile,
} from "@/api/imports";
import type { BundleMember, CalibreBundle } from "@/features/import/bundle";
import {
  cheapMembers,
  isEbookMember,
  narrowedTo,
} from "@/features/import/bundle";
import { ConnectorGuide } from "@/features/import/ConnectorGuide";
import { ProposalList } from "@/features/import/ProposalList";
import { NoResultRow, RowExcludeControl } from "@/features/import/RowControls";
import { describeRowError } from "@/features/import/errors";
import { useItemTypes } from "@/features/library/useItemTypes";
import { weightClass } from "@/features/library/insights";
import { DirectoryPicker } from "@/features/import/DirectoryPicker";
import { ExportPanel } from "@/features/export/ExportPanel";
import { ExportPicker } from "@/features/import/ExportPicker";
import { FolderPicker } from "@/features/import/FolderPicker";
import { SourceDropZone } from "@/features/import/SourceDropZone";
import { scoreChipClass, scoreChipShape } from "@/lib/score";
import { cn } from "@/lib/utils";
import { TriagePage } from "@/pages/TriagePage";

/** A refusal as the screen shows it: what happened, and what to do about it. */
interface ImportFailure {
  readonly message: string;
  readonly action: string | null;
}

interface AttachmentFailure {
  readonly path: string;
  readonly message: string;
}

interface AttachmentProgress {
  readonly total: number;
  readonly completed: number;
  readonly current: string | null;
  readonly failures: AttachmentFailure[];
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
/**
 * The tab that lets data leave.
 *
 * Unnumbered in the workflow strip beside it (Sprint 069): Import and Triage are
 * steps of one flow, and Export is not a step of importing — it is the same screen's
 * other direction (`docs/export-proposal.md` §3).
 */
export const EXPORT_TAB = "export";
const IMPORT_STEP = "import";

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
  // The typed-or-pasted half of the list's source (Sprint 085): the editor is
  // the owner's window into what he uploaded — a dropped file fills it, a
  // correction re-types it, and three typed rows import with no file at all.
  const [typedList, setTypedList] = useState("");
  // The owners' 2026-09-15 ask: "most queries work without them." Keyed by
  // connector so switching tabs never carries one source's answer.
  const [noCreatorsByImporter, setNoCreatorsByImporter] = useState<
    Record<string, boolean>
  >({});
  // The chosen separator, keyed by connector (empty = auto, the sniffed one).
  const [delimitersByImporter, setDelimitersByImporter] = useState<
    Record<string, string>
  >({});
  const [libraryPath, setLibraryPath] = useState("");
  const [bundle, setBundle] = useState<CalibreBundle | null>(null);
  const [exportFiles, setExportFiles] = useState<File[]>([]);
  const [filesToAttach, setFilesToAttach] = useState<BundleMember[]>([]);
  const [attachmentProgress, setAttachmentProgress] =
    useState<AttachmentProgress | null>(null);
  /** Which alternates are open, keyed by their own field name. */
  const [openAlternates, setOpenAlternates] = useState<Record<string, boolean>>(
    {},
  );
  /**
   * Which libraries this import is for, per connector.
   *
   * Keyed by connector so switching tabs does not carry one source's answer over to
   * another, and absent means "everything it declares" — which is what the boxes show
   * ticked and the only thing a single-domain connector can mean.
   */
  const [targets, setTargets] = useState<Record<string, string[]>>({});
  // The single-pick library choice for connectors whose rows cannot route
  // themselves (Sprint 084's list): one domain per batch, chosen before the
  // file can be interpreted.
  const [domainPicks, setDomainPicks] = useState<Record<string, string>>({});

  /**
   * What the picked library calls the second column of a list (Sprint 084):
   * the domain's own creators word — Author for books, Artist for albums —
   * falling back to the neutral "Creator" the way every label falls back
   * when a domain has not said otherwise.
   */
  const creatorWordFor = (importer: ImporterDefinition) => {
    const picked = domainPicks[importer.id] ?? importer.item_types[0];
    const known = Array.isArray(itemTypes.data)
      ? itemTypes.data.find((type) => type.id === picked)
      : undefined;
    const creators = known?.fields.find((field) => field.name === "creators");
    return creators?.label ?? "Creator";
  };
  const [skipped, setSkipped] = useState<{
    held: number;
    reason: string | null;
  } | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  /**
   * The column mapping a list connector asks for, as the owner typed it —
   * column numbers as strings, sent with the next preview only (Sprint 083).
   */
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>(
    {},
  );
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
    // Focus the preview heading when a NEW batch arrives, not on every poll
    // tick or owner answer: a searching batch re-reads itself every 2 s and
    // every answer refreshes the preview, and each refocus pulled the page
    // back to the top mid-browse (the owner's 2026-09-14 report).
    if (preview) heading.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.batch_id]);
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
    asked === TRIAGE_TAB ||
    asked === EXPORT_TAB ||
    importers.some((importer) => importer.id === asked)
      ? asked
      : fallbackSource;
  const triageActive = source === TRIAGE_TAB;
  const exportActive = source === EXPORT_TAB;

  useEffect(() => setError(null), [source]);

  // A staged source, its preview and its undo window belong to the connector
  // that produced them. Moving to another connector starts clean; moving to
  // Triage or Export and back does not, because neither is a connector — and
  // the undo window is only reachable from the result panel it would
  // otherwise discard. The walkthrough found this: after a Goodreads commit,
  // the Calibre tab showed the Goodreads result and no Calibre form at all.
  const belongsTo = useRef("");
  useEffect(() => {
    if (
      !source ||
      source === TRIAGE_TAB ||
      source === EXPORT_TAB ||
      belongsTo.current === source
    )
      return;
    belongsTo.current = source;
    setFile(null);
    setLibraryPath("");
    setBundle(null);
    setExportFiles([]);
    setFilesToAttach([]);
    setAttachmentProgress(null);
    setOpenAlternates({});
    setSkipped(null);
    setPreview(null);
    setResult(null);
    setUndoResult(null);
    setChoices({});
    setConfirmUndo(false);
  }, [source]);

  const selectTab = (value: string) => {
    if (value !== TRIAGE_TAB && value !== EXPORT_TAB) {
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

  const selectStep = (value: string) => {
    selectTab(
      value === TRIAGE_TAB || value === EXPORT_TAB
        ? value
        : fallbackSource || importers[0]?.id || "",
    );
  };

  const matching = preview?.state === "matching";
  // A searching batch is polled through the idempotent preview read — the
  // response carries the job's live counts, and flips its own state to
  // `previewed` the moment the queue drains. The poll stops itself then.
  useEffect(() => {
    if (!preview || preview.state !== "matching" || !source) return;
    const timer = window.setInterval(() => {
      void getPreview(source, preview.batch_id)
        .then((fresh) => setPreview(fresh))
        .catch(() => {
          /* the next tick retries; a batch deleted mid-poll is not a screen error */
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [preview, source]);

  const unresolved =
    preview?.records.filter(
      (record) =>
        record.planned_action === "ambiguous" && !choices[record.record_id],
    ).length ?? 0;
  const ready =
    (preview?.summary.ready ?? 0) + (preview?.summary.ambiguous ?? 0);
  const activeImporter = importers.find((importer) => importer.id === source);
  // The list connector's owners' checkbox (2026-09-15), keyed by connector so
  // switching tabs never carries one source's answer into another's request.
  const noCreators = !!noCreatorsByImporter[activeImporter?.id ?? ""];
  const chosenDelimiter = delimitersByImporter[activeImporter?.id ?? ""] ?? "";

  /**
   * A one-line peek at how the current config would read the typed or
   * dropped rows (the owner's 2026-09-15 ask, kept deliberately cheap):
   * the first data row, split on the chosen separator — or the sniffed one
   * when Auto — with the columns the mapping would pick named above them.
   * Display only; the preview remains the truth.
   */
  const sampleRowFor = (importer: ImporterDefinition): string => {
    const source = typedList.trim() || "";
    const lines = source.split(/\r\n|\n/).filter(Boolean);
    const data = lines.length > 1 ? lines[1] : (lines[0] ?? "");
    if (!data) return "";
    const pick = delimitersByImporter[importer.id] || "";
    const semis = (data.match(/;/g) ?? []).length;
    const tabs = (data.match(/\t/g) ?? []).length;
    const commas = (data.match(/,/g) ?? []).length;
    const sniffed =
      semis > commas && semis >= tabs
        ? ";"
        : tabs > commas && tabs > semis
          ? "\t"
          : ",";
    const separator = pick || sniffed;
    const cells = data.split(separator).map((cell) => cell.trim());
    const titleIndex = Number(columnMapping["title_column"]) - 1;
    const creatorIndex = Number(columnMapping["author_column"]) - 1;
    const title =
      cells[Number.isFinite(titleIndex) ? titleIndex : 0] ?? cells[0];
    const creator =
      cells[Number.isFinite(creatorIndex) ? creatorIndex : 1] ?? cells[1] ?? "";
    return noCreatorsByImporter[importer.id]
      ? `Sample: ${title}`
      : `Sample: ${[title, creator].filter(Boolean).join(" | ")}`;
  };
  // A connector that can fill more than one library needs their names for the
  // target checkboxes, and a failed preview row needs the domain's own field
  // labels to describe what went wrong (AC3) — fetched only once either is
  // actually true, since most visits need neither.
  const itemTypes = useItemTypes(
    importers.some((importer) => importer.item_types.length > 1) ||
      // The list connector needs the domains' names and creators words for its
      // dropdown and mapping labels (Sprint 084).
      importers.some(
        (importer) => importer.input.single_domain_pick === true,
      ) ||
      (preview?.records.some((record) => record.errors.length > 0) ?? false),
  );
  // A record carries no domain of its own — only a connector that fills more
  // than one library could need it, and none that ships today does — so a
  // failed row's field label is resolved against the single domain the active
  // importer declares. A future multi-domain connector without a per-record
  // type falls back to the honest, still-legible default (AC3's humanized
  // fallback) rather than guessing which domain a row belongs to.
  const recordDomain =
    activeImporter?.item_types.length === 1 && Array.isArray(itemTypes.data)
      ? itemTypes.data.find((type) => type.id === activeImporter.item_types[0])
      : undefined;

  /**
   * What this connector is currently set to bring in. Everything, by default —
   * except a connector whose target is a single-pick library choice (Sprint
   * 084's list): a list row carries no identity to route it, so the pick is
   * the batch's, defaults to the first declared library, and is exactly one.
   */
  const chosenFor = (importer: ImporterDefinition) => {
    if (importer.input.single_domain_pick)
      return [domainPicks[importer.id] ?? importer.item_types[0]];
    return targets[importer.id] ?? importer.item_types;
  };

  /** The library's own name for a domain, falling back to its id (DEC-080). */
  const libraryLabel = (itemType: string) =>
    (Array.isArray(itemTypes.data)
      ? itemTypes.data.find((type) => type.id === itemType)?.label
      : undefined) ?? itemType;

  /**
   * A checkbox per declared domain, and nothing at all for a connector with one.
   *
   * The connector declares what it can produce and the screen renders that
   * declaration; unticking a box narrows what the *request* asks for, and the
   * server drops the rest (DEC-106). A choice of one is not a choice, so Goodreads
   * and Calibre look exactly as they always did.
   */
  const renderTargets = (importer: ImporterDefinition) => {
    // A single-pick connector chose its one library above the file input;
    // tick-many checkboxes would promise a mixed batch the reader refuses.
    if (importer.input.single_domain_pick) return null;
    if (importer.item_types.length < 2) return null;
    const chosen = chosenFor(importer);
    return (
      <fieldset className="rounded-2xl border border-border px-4 py-3">
        <legend className="px-1 text-sm font-semibold">
          What should this import?
        </legend>
        <div className="mt-1 flex flex-wrap gap-x-6 gap-y-2">
          {importer.item_types.map((itemType) => {
            const id = `${importer.id}-target-${itemType}`;
            const ticked = chosen.includes(itemType);
            return (
              <div key={itemType} className="flex items-center gap-2">
                <Checkbox
                  id={id}
                  checked={ticked}
                  // The last box may not be unticked: an import that brings in
                  // nothing is a refusal the server would have to make anyway,
                  // and meeting it after choosing a file is worse than not
                  // being offered it.
                  disabled={ticked && chosen.length === 1}
                  onCheckedChange={() =>
                    setTargets((current) => ({
                      ...current,
                      [importer.id]: ticked
                        ? chosen.filter((row) => row !== itemType)
                        : importer.item_types.filter(
                            (row) => row === itemType || chosen.includes(row),
                          ),
                    }))
                  }
                />
                <Label htmlFor={id} className="font-normal">
                  {libraryLabel(itemType)}
                </Label>
              </div>
            );
          })}
        </div>
      </fieldset>
    );
  };

  /**
   * Which of a connector's inputs the reader actually filled in, if any.
   *
   * A connector may offer several (DEC-081, generalized), so "is this ready to
   * preview" is a question about the whole tab rather than about one field. The
   * primary wins when more than one is filled, because it is the one the tab
   * leads with.
   */
  const readyInput = (
    importer: ImporterDefinition | undefined,
  ): {
    spec: ImportInputSpec;
    source: File | string | BundleMember[] | File[];
  } | null => {
    if (!importer) return null;
    for (const spec of [importer.input, ...importer.input.alternates]) {
      if (
        spec.kind === "directory" &&
        bundle?.database &&
        bundle.members.length
      )
        return { spec, source: bundle.members };
      if (spec.kind === "export" && exportFiles.length > 0)
        return { spec, source: exportFiles };
      if (spec.kind === "upload" && file) return { spec, source: file };
      if (spec.kind === "upload" && typedList.trim())
        return {
          spec,
          // The typed rows travel as the upload the connector declared —
          // same route, same reader, no new API surface. The name says
          // what it is: not a file the owner chose.
          source: new File([typedList], "pasted-list.csv", {
            type: "text/csv",
          }),
        };
      if (spec.kind === "path" && libraryPath.trim())
        return { spec, source: libraryPath.trim() };
    }
    return null;
  };

  /**
   * The bytes to actually send, after asking the server what it wants.
   *
   * The plan is an optimisation and is never load-bearing: if it fails for any
   * reason the whole bundle goes, and the screen says so. A broken optimisation
   * must not turn a working import into a broken one (DEC-082).
   */
  const sendable = async (
    importer: ImporterDefinition,
    submission: {
      spec: ImportInputSpec;
      source: File | string | BundleMember[] | File[];
    },
  ): Promise<File | string | BundleMember[] | File[]> => {
    if (submission.spec.kind !== "directory") {
      setFilesToAttach([]);
      return submission.source;
    }
    if (!bundle) return submission.source;
    let wanted = bundle.members.map((member) => member.path);
    try {
      if (submission.spec.incremental) {
        const plan = await planImport(
          importer,
          submission.spec,
          cheapMembers(bundle),
          bundle.members,
        );
        setSkipped(
          plan.holding > 0 || plan.reason
            ? { held: plan.holding, reason: plan.reason }
            : null,
        );
        wanted = plan.wanted;
      }
    } catch {
      setSkipped({
        held: 0,
        reason:
          "Could not check what is already imported, so every selected file will be sent.",
      });
    }
    const selected = narrowedTo(bundle, wanted);
    setFilesToAttach(selected.filter(isEbookMember));
    // Ebooks are offered to the planner now, but their bytes travel one at a time
    // only after commit. This keeps the preview request bounded by the source cap
    // and each attachment request bounded by the attachment cap (DEC-083).
    return selected.filter((member) => !isEbookMember(member));
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
          onBundle={(next) => {
            setBundle(next);
            setFilesToAttach([]);
            setAttachmentProgress(null);
          }}
          attachmentMaxBytes={importer.attachment_max_bytes}
        />
      );
    if (spec.kind === "export")
      return (
        <ExportPicker
          spec={spec}
          inputId={inputId}
          files={exportFiles}
          onFiles={setExportFiles}
        />
      );
    if (spec.kind === "upload")
      return (
        <div className="space-y-3">
          {spec.single_domain_pick && importer.item_types.length > 1 && (
            // The library choice comes before the file: the connector cannot
            // interpret the list — which headers are titles, whether a second
            // column is even required — until it knows whose vocabulary to
            // read with (Sprint 084). Rendered from the declaration, not a
            // branch on the connector's name.
            <div>
              <label htmlFor={`${importer.id}-domain`} className="block">
                <span className="text-sm text-muted-foreground">
                  Which library is this list for?
                </span>
                <select
                  id={`${importer.id}-domain`}
                  className="mt-1 h-11 w-full rounded-md border border-input bg-surface-raised px-3 text-base focus-ring"
                  value={domainPicks[importer.id] ?? importer.item_types[0]}
                  onChange={(event) =>
                    setDomainPicks((current) => ({
                      ...current,
                      [importer.id]: event.target.value,
                    }))
                  }
                >
                  {importer.item_types.map((itemType) => {
                    const known = Array.isArray(itemTypes.data)
                      ? itemTypes.data.find((type) => type.id === itemType)
                      : undefined;
                    return (
                      <option key={itemType} value={itemType}>
                        {known ? known.label : itemType}
                      </option>
                    );
                  })}
                </select>
              </label>
            </div>
          )}
          <SourceDropZone
            importer={importer}
            inputId={inputId}
            file={file}
            onFile={(next) => {
              setFile(next);
              // A dropped file lands in the editor too, so "check what I
              // uploaded and make small corrections" is literal: the owner
              // sees the bytes and can re-type them. The file stays the
              // source until the editor is edited (last one edited wins).
              // (A FileReader, not File.text(): jsdom's File carries no
              // `text()`, and the editor must fill in the component tests
              // exactly as it does in the browser.)
              if (next && next.type.startsWith("text/")) {
                const reader = new FileReader();
                reader.onload = () => setTypedList(String(reader.result ?? ""));
                reader.onerror = () => undefined;
                reader.readAsText(next);
              }
            }}
          />

          {spec.flags?.includes("no_creators") && (
            <div>
              <label htmlFor={`${importer.id}-typed`} className="block">
                <span className="text-sm text-muted-foreground">
                  Or type your list here
                </span>
                <textarea
                  id={`${importer.id}-typed`}
                  className="mt-1 min-h-32 w-full rounded-md border border-input bg-surface-raised px-3 py-2 font-mono text-sm focus-ring"
                  value={typedList}
                  placeholder={"Título,Autor\nRayuela,Julio Cortázar"}
                  onChange={(event) => {
                    setTypedList(event.target.value);
                    // Editing the editor makes it the source; the file no
                    // longer speaks for the batch.
                    setFile(null);
                  }}
                />
              </label>
              <p className="mt-1 text-xs text-muted-foreground">
                Editing here after dropping a file re-types the list — the
                editor is what gets imported.
              </p>
            </div>
          )}
          {/* The connector's declared fields, rendered from the declaration:
              a list asks which columns hold the title and the author (Sprint
              083), and every connector with no fields shows nothing — no
              branch on which connector this is (the same rule the guide and
              the target checkboxes follow). */}
          {spec.fields && spec.fields.length > 0 && (
            <fieldset
              // One grid so every control shares two baselines: labels on
              // one line, h-11 controls on the next — the owner's alignment
              // ask. Two columns on a phone, one tidy row from `sm` up.
              className="grid grid-cols-2 gap-x-3 gap-y-2 rounded-lg border border-border p-3 sm:grid-cols-4"
              aria-label="Column mapping"
            >
              {spec.fields.map((name) =>
                name === "delimiter" ? (
                  <label key={name} className="flex min-w-0 flex-col gap-1">
                    <span className="text-sm text-muted-foreground">
                      Separator
                    </span>
                    <select
                      aria-label="Separator"
                      className="h-11 w-full rounded-md border border-input bg-surface-raised px-3 text-base focus-ring"
                      value={delimitersByImporter[importer.id] ?? ""}
                      onChange={(event) =>
                        setDelimitersByImporter((current) => ({
                          ...current,
                          [importer.id]: event.target.value,
                        }))
                      }
                    >
                      <option value="">Auto</option>
                      <option value=",">Comma</option>
                      <option value=";">Semicolon</option>
                      <option value="&#9;">Tab</option>
                    </select>
                  </label>
                ) : (
                  <label key={name} className="flex min-w-0 flex-col gap-1">
                    <span className="text-sm text-muted-foreground">
                      {name === "title_column"
                        ? "Title is column"
                        : name === "author_column"
                          ? `${creatorWordFor(importer)} is column`
                          : name}
                    </span>
                    <Input
                      type="number"
                      min={1}
                      className="h-11 w-full"
                      value={columnMapping[name] ?? ""}
                      placeholder="auto"
                      onChange={(event) =>
                        setColumnMapping((old) => ({
                          ...old,
                          [name]: event.target.value,
                        }))
                      }
                    />
                  </label>
                ),
              )}
              {spec.flags?.includes("no_creators") && (
                <div className="flex min-w-0 flex-col gap-1">
                  {/* An invisible label line so the checkbox lands on the
                      same baseline as the number inputs beside it. */}
                  <span
                    aria-hidden="true"
                    className="invisible text-sm text-muted-foreground"
                  >
                    Creators
                  </span>
                  <label className="flex h-11 items-center gap-2">
                    <Checkbox
                      checked={noCreators}
                      onCheckedChange={(checked) =>
                        setNoCreatorsByImporter((current) => ({
                          ...current,
                          [importer.id]: checked === true,
                        }))
                      }
                      aria-label="No creators column"
                    />
                    <span className="text-sm text-muted-foreground">
                      No creators
                    </span>
                  </label>
                </div>
              )}
              <p className="col-span-full text-xs text-muted-foreground">
                Leave them empty and the columns are found from the headers; the
                first two columns are the fallback.
              </p>
              {spec.fields.includes("delimiter") && (
                <p
                  className="col-span-full font-mono text-xs text-muted-foreground"
                  aria-live="polite"
                >
                  {sampleRowFor(importer)}
                </p>
              )}
            </fieldset>
          )}
        </div>
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

  const workflowStrip = (
    <TabsList
      aria-label="Import workflow"
      className="grid h-auto w-full grid-cols-3 gap-2 rounded-2xl bg-surface p-2"
    >
      <TabsTrigger
        value={IMPORT_STEP}
        className="h-auto min-w-0 justify-start gap-3 whitespace-normal rounded-xl px-4 py-3 text-left"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
          1
        </span>
        <span className="min-w-0">
          <span className="block font-semibold">Import</span>
          <span className="block text-xs font-normal text-muted-foreground">
            Choose and preview a source
          </span>
        </span>
      </TabsTrigger>
      <TabsTrigger
        value={TRIAGE_TAB}
        className="h-auto min-w-0 justify-start gap-3 whitespace-normal rounded-xl px-4 py-3 text-left"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
          2
        </span>
        <span className="min-w-0">
          <span className="block font-semibold">Triage</span>
          <span className="block text-xs font-normal text-muted-foreground">
            Review entries individually or in bulk
          </span>
        </span>
      </TabsTrigger>
      {/* Unnumbered on purpose: Import and Triage are steps of one flow, and
      Export is not a step of importing — it is the same screen's other
      direction (docs/export-proposal.md §3, Sprint 069 deliverable 1). */}
      <TabsTrigger
        value={EXPORT_TAB}
        className="h-auto min-w-0 justify-start gap-3 whitespace-normal rounded-xl px-4 py-3 text-left"
      >
        <span className="min-w-0">
          <span className="block font-semibold">Export</span>
          <span className="block text-xs font-normal text-muted-foreground">
            Take your library elsewhere
          </span>
        </span>
      </TabsTrigger>
    </TabsList>
  );

  const sourceStrip = (
    // Scrolls within its own box below its breakpoint instead of pushing the
    // document sideways — DomainStrip's own fix for the same class of defect
    // (DEC-134), applied here to a seven-importer TabsList that overflowed a
    // 390px viewport by about 205px (DEC-137, found by Sprint 070's own
    // walkthrough, out of that sprint's scope, fixed here at the owner's
    // direction).
    <TabsList
      aria-label="Import source"
      // `justify-start`, never the shadcn default `justify-center`: centered
      // flex content overflowing a scroll box paints left of it, unreachable
      // (Sprint 085's walkthrough). Left-anchored, the overflow scrolls.
      // No pill background: the strip is a quiet row of two-line cards —
      // the connector's name in the reading voice, the library it serves as
      // a caption beneath — and the active card is shown by the ring, not by
      // a filled well (the owner's 2026-09-15 "ugly" report).
      className="flex h-auto min-w-0 max-w-full justify-start gap-2 overflow-x-auto bg-transparent p-0"
    >
      {importers.map((importer) => (
        <TabsTrigger
          key={importer.id}
          value={importer.id}
          className="min-h-11 shrink-0 items-start gap-0 rounded-lg border border-transparent px-3 py-2 text-left data-[state=active]:border-border data-[state=active]:bg-surface-raised data-[state=active]:shadow-sm"
        >
          {/* Two lines: the name is the anchor, the library caption reads
              beneath it — from the connector's own `item_types`, never a
              hardcoded list. The caption is plain text, deliberately not a
              colored chip (no semantic collision, the ScorePicker rule). */}
          <span className="block min-w-0 text-sm font-medium leading-tight">
            {importer.label}
          </span>
          <span className="mt-0.5 block truncate text-[11px] leading-tight text-muted-foreground">
            {importer.item_types.length > 1
              ? "Any library"
              : ((Array.isArray(itemTypes.data)
                  ? itemTypes.data.find(
                      (type) => type.id === importer.item_types[0],
                    )?.label
                  : undefined) ?? importer.item_types[0])}
          </span>
        </TabsTrigger>
      ))}
    </TabsList>
  );

  return (
    <Tabs
      value={
        exportActive ? EXPORT_TAB : triageActive ? TRIAGE_TAB : IMPORT_STEP
      }
      onValueChange={selectStep}
    >
      <div className="mx-auto max-w-7xl px-5 pt-7 sm:px-8">{workflowStrip}</div>
      <TabsContent value={IMPORT_STEP} className="mt-0">
        <Tabs value={source} onValueChange={selectTab} asChild>
          <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
            <PageHeader
              back
              title="Import"
              lede="Preview a source before anything enters your library. Existing values are preserved when a re-sync only supplies missing metadata."
            />
            {importers.length > 0 && (
              <section className="mt-7" aria-labelledby="import-source-heading">
                <h2
                  id="import-source-heading"
                  className="mb-3 text-sm font-semibold text-foreground"
                >
                  Choose an import source
                </h2>
                {sourceStrip}
              </section>
            )}
            {!preview && importers.length > 0 && (
              <>
                {/* The panel each trigger names has to exist. Without it Radix still
              writes `aria-controls` pointing at nothing, which axe reports as a
              critical invalid attribute value and which leaves a screen reader
              unable to reach the fields the tab just switched to (DEC-038). */}
                <form
                  className="mt-8 space-y-5 rounded-xl border border-border bg-surface p-5"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const submission = readyInput(activeImporter);
                    if (!submission) return;
                    setPending(true);
                    setError(null);
                    setSkipped(null);
                    const importer = activeImporter as ImporterDefinition;
                    void sendable(importer, submission)
                      .then((source) =>
                        // A connector that declared extra fields gets them
                        // appended to the same upload, keyed by connector so
                        // switching tabs never carries one source's mapping
                        // into another's request.
                        Object.keys(columnMapping).length > 0 ||
                        (noCreators && !!submission.spec.flags?.length) ||
                        (!!chosenDelimiter &&
                          !!submission.spec.fields?.includes("delimiter"))
                          ? previewImportWithOptions(
                              importer,
                              submission.spec,
                              source,
                              Object.fromEntries([
                                ...Object.entries(columnMapping)
                                  .filter(([name]) =>
                                    submission.spec.fields!.includes(name),
                                  )
                                  // The screen speaks 1-based column
                                  // numbers; the reader's contract is
                                  // 0-based.
                                  .map(([name, value]) => [
                                    name,
                                    String(Number(value) - 1),
                                  ])
                                  .filter(([, value]) => Number(value) >= 0),
                                // The owner's checkbox and separator ride
                                // the same options channel the mapping does.
                                ...(noCreators
                                  ? ([["no_creators", "true"]] as const)
                                  : []),
                                ...(chosenDelimiter
                                  ? ([["delimiter", chosenDelimiter]] as const)
                                  : []),
                              ]),
                              chosenFor(importer),
                            )
                          : previewImport(
                              importer,
                              submission.spec,
                              source,
                              chosenFor(importer),
                            ),
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
                      {renderTargets(importer)}
                      {/* A short, distinct lead for the primary, the same role an
                      alternate's own toggle text plays below it. Shown only
                      alongside a guide — `ConnectorGuide` already renders `help`
                      itself when there is no guide to show instead, so the two
                      never duplicate. */}
                      {importer.input.guide.length > 0 &&
                        importer.input.help && (
                          <p className="text-sm font-medium text-foreground">
                            {importer.input.help}
                          </p>
                        )}
                      {renderInput(importer, importer.input, "")}
                      {/* Other ways in, each beneath the primary. One deep by
                      contract, so this never recurses further (DEC-081,
                      generalized). */}
                      {importer.input.alternates.map((alternate, index) => {
                        const open = openAlternates[alternate.field] ?? false;
                        const panelId = `${importer.id}-alternate-${alternate.field}`;
                        return (
                          // A controlled disclosure rather than `<details>`: this is
                          // another way in, so it needs an explicit expanded state
                          // that a screen reader announces and a test can drive.
                          <div
                            key={alternate.field}
                            className="rounded-2xl border border-border px-4 py-3"
                          >
                            <Button
                              type="button"
                              variant="ghost"
                              aria-expanded={open}
                              aria-controls={panelId}
                              className="h-auto min-h-8 w-full justify-start whitespace-normal rounded-lg px-2 py-1.5 text-left text-sm font-normal text-muted-foreground"
                              onClick={() =>
                                setOpenAlternates((current) => ({
                                  ...current,
                                  [alternate.field]: !open,
                                }))
                              }
                            >
                              {alternate.help ??
                                `Or use another way to import ${importer.label}`}
                            </Button>
                            {open && (
                              <div id={panelId} className="mt-4 space-y-4">
                                {alternate.guide.length > 0 && (
                                  <ConnectorGuide
                                    importer={importer}
                                    spec={alternate}
                                    headingId={`${panelId}-guide-heading`}
                                  />
                                )}
                                {renderInput(
                                  importer,
                                  alternate,
                                  `-alt-${index}`,
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
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
            {skipped && (
              <p className="mt-4 text-sm text-muted-foreground" role="status">
                {skipped.held > 0
                  ? `Skipped ${skipped.held} ${skipped.held === 1 ? "file" : "files"} — ${skipped.reason}.`
                  : skipped.reason}
              </p>
            )}
            {error && (
              // The action is the connector's, not this screen's: only Calibre knows
              // that a locked database means "close Calibre and try again" (DEC-080).
              <div
                className="mt-4 rounded-xl bg-destructive/10 p-4"
                role="alert"
              >
                <p className="text-destructive">{error.message}</p>
                {error.action && (
                  <p className="mt-1 text-sm text-foreground">{error.action}</p>
                )}
              </div>
            )}
            {preview && !result && (
              <section className="mt-8">
                <h2
                  ref={heading}
                  tabIndex={-1}
                  className="text-2xl font-semibold"
                >
                  Preview: {preview.summary.total} rows
                </h2>
                <p
                  className="mt-2 flex flex-wrap items-baseline gap-x-1"
                  role="status"
                >
                  {/* Three counts describing one whole — the same rule the
                      shelves list and the status facets apply to theirs
                      (deliverable 5) — so the number that dominates the batch
                      reads as dominant, not identical in weight to the two
                      that don't. */}
                  {(() => {
                    const max = Math.max(
                      preview.summary.ready,
                      preview.summary.ambiguous,
                      preview.summary.errors,
                      1,
                    );
                    return (
                      <>
                        <span
                          className={weightClass(preview.summary.ready, max)}
                        >
                          {preview.summary.ready} ready
                        </span>
                        <span>·</span>
                        <span
                          className={weightClass(
                            preview.summary.ambiguous,
                            max,
                          )}
                        >
                          {preview.summary.ambiguous} need a choice
                        </span>
                        <span>·</span>
                        <span
                          className={weightClass(preview.summary.errors, max)}
                        >
                          {preview.summary.errors} have errors
                        </span>
                      </>
                    );
                  })()}
                </p>
                {matching && preview.search_progress && (
                  <p
                    className="mt-2 text-sm text-muted-foreground"
                    role="status"
                    data-testid="search-progress"
                  >
                    {preview.search_progress.wait_reason ===
                    "provider_quota_exhausted"
                      ? `Searching paused for today's provider budget; it resumes automatically. ${
                          preview.search_progress.searched
                        } of ${preview.search_progress.total} rows searched.`
                      : `Searching for matches: ${
                          preview.search_progress.searched
                        } of ${preview.search_progress.total} rows searched.`}
                  </p>
                )}
                {/* What the import left behind, on its own line and never counted
                as an error. The two are kept apart because they are different
                answers: one is a library you did not choose, the other is a kind
                of thing no library here holds (DEC-106). */}
                {(preview.summary.skipped_not_requested > 0 ||
                  preview.summary.skipped_unsupported > 0) && (
                  <p
                    className="mt-1 text-sm text-muted-foreground"
                    data-testid="import-skipped"
                  >
                    {[
                      preview.summary.skipped_not_requested > 0
                        ? `${preview.summary.skipped_not_requested} ${preview.summary.skipped_not_requested === 1 ? "row is" : "rows are"} for libraries you did not choose`
                        : null,
                      preview.summary.skipped_reasons.length > 0
                        ? `${preview.summary.skipped_reasons
                            .map((row) => `${row.count} ${row.reason}`)
                            .join(", ")} — not a kind this tracks`
                        : preview.summary.skipped_unsupported > 0
                          ? `${preview.summary.skipped_unsupported} rows are not a kind this tracks`
                          : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                )}
                <div className="mt-5 space-y-3">
                  {preview.records.map((record) => (
                    <article
                      key={record.record_id}
                      className={cn(
                        "rounded-xl border border-border bg-surface p-4",
                        record.planned_action === "excluded" && "opacity-60",
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="font-semibold">
                          {record.title || `Row ${record.row_number}`}
                        </h3>
                        {!result && !matching && (
                          // The owner's 2026-09-14 decision: a row the owner
                          // does not want can leave the import entirely, not
                          // only land as typed. Placed on the row itself so it
                          // reads as a decision about THIS row, next to the
                          // title it is a decision about.
                          <RowExcludeControl
                            recordId={record.record_id}
                            excluded={record.planned_action === "excluded"}
                            batchId={preview.batch_id}
                            importerId={source}
                            onChanged={() => {
                              void getPreview(source, preview.batch_id)
                                .then((fresh) => setPreview(fresh))
                                .catch(() => {
                                  /* the next poll or action reads fresh */
                                });
                            }}
                          />
                        )}
                      </div>
                      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
                        <span>
                          {record.creators.join(", ") || "Creator missing"}
                        </span>
                        {/* The score every other surface paints — the same
                            band the library card and the detail page use for
                            this score, not prose (finding 2, AC2). */}
                        {record.score !== null && (
                          <>
                            <span aria-hidden="true">·</span>
                            <span
                              className={cn(
                                scoreChipShape,
                                scoreChipClass(record.score),
                              )}
                            >
                              {record.score}
                            </span>
                            {record.score_provisional && (
                              <span className="text-xs">(provisional)</span>
                            )}
                          </>
                        )}
                        {record.suggested_status && (
                          <>
                            <span aria-hidden="true">·</span>
                            <span>suggested {record.suggested_status}</span>
                          </>
                        )}
                      </p>
                      {record.cover_staged && (
                        // A fact about where the cover came from, not a score
                        // — it stops borrowing the emerald that means a 9 or a
                        // 10 everywhere else (finding 1, AC1).
                        <span className="mt-1 inline-block rounded-full bg-surface-raised px-2 py-0.5 text-xs text-muted-foreground">
                          Local cover staged
                        </span>
                      )}
                      {record.errors.map((row, index) => (
                        <p
                          key={`${row.field}-${index}`}
                          className="text-sm text-destructive"
                        >
                          {describeRowError(row, recordDomain)}
                        </p>
                      ))}
                      {(record.proposals?.length ?? 0) > 0 && !result && (
                        <ProposalList
                          recordId={record.record_id}
                          title={record.title}
                          author={record.creators.join(", ")}
                          proposals={record.proposals}
                          batchId={preview.batch_id}
                          importerId={source}
                          matching={matching}
                          onAnswered={() => {
                            void getPreview(source, preview.batch_id)
                              .then((fresh) => setPreview(fresh))
                              .catch(() => {
                                /* answered; the next poll or action reads fresh */
                              });
                          }}
                        />
                      )}
                      {record.proposals?.length === 0 &&
                        !result &&
                        !matching && (
                          // A row the search finished on with nothing to show
                          // still owns its affordances: the edit-and-re-search
                          // form, and the way out of the import entirely.
                          <NoResultRow
                            recordId={record.record_id}
                            title={record.title}
                            author={record.creators.join(", ")}
                            batchId={preview.batch_id}
                            importerId={source}
                            onAnswered={() => {
                              void getPreview(source, preview.batch_id)
                                .then((fresh) => setPreview(fresh))
                                .catch(() => {
                                  /* answered; the next poll or action reads fresh */
                                });
                            }}
                          />
                        )}
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
                  disabled={
                    pending || matching || unresolved > 0 || ready === 0
                  }
                  onClick={() => {
                    setPending(true);
                    setError(null);
                    void (async () => {
                      const committed = await commitImport(
                        source,
                        preview.batch_id,
                        Object.entries(choices).map(([recordId, value]) => ({
                          record_id: Number(recordId),
                          item_id: value === "new" ? null : value,
                        })),
                      );
                      setResult(committed);
                      if (filesToAttach.length > 0) {
                        const failures: AttachmentFailure[] = [];
                        setAttachmentProgress({
                          total: filesToAttach.length,
                          completed: 0,
                          current: filesToAttach[0].path,
                          failures,
                        });
                        for (const [index, member] of filesToAttach.entries()) {
                          setAttachmentProgress({
                            total: filesToAttach.length,
                            completed: index,
                            current: member.path,
                            failures: [...failures],
                          });
                          try {
                            await uploadImportFile(
                              source,
                              committed.batch_id,
                              member,
                            );
                          } catch (reason) {
                            failures.push({
                              path: member.path,
                              message:
                                reason instanceof Error
                                  ? reason.message
                                  : "That file could not be stored.",
                            });
                          }
                          setAttachmentProgress({
                            total: filesToAttach.length,
                            completed: index + 1,
                            current: null,
                            failures: [...failures],
                          });
                        }
                      }
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
                    })()
                      .catch((reason: Error) => setError(asFailure(reason)))
                      .finally(() => setPending(false));
                  }}
                >
                  {pending
                    ? "Importing…"
                    : matching
                      ? "Waiting for the search to finish…"
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
                {attachmentProgress && (
                  <div className="mt-3 text-sm" aria-live="polite">
                    <p>
                      {attachmentProgress.current
                        ? `Attaching ebook ${attachmentProgress.completed + 1} of ${attachmentProgress.total}: ${attachmentProgress.current}`
                        : `Attached ${attachmentProgress.total - attachmentProgress.failures.length} of ${attachmentProgress.total} ${attachmentProgress.total === 1 ? "ebook" : "ebooks"}.`}
                    </p>
                    {attachmentProgress.failures.length > 0 && (
                      <div className="mt-2 text-destructive">
                        <p>These files could not be attached:</p>
                        <ul className="mt-1 list-disc pl-5">
                          {attachmentProgress.failures.map((failure) => (
                            <li key={failure.path}>
                              {failure.path} — {failure.message}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
                {/* Imported rows land `unsorted`, and the library's default view
              excludes `unsorted`, so a successful import used to look like a
              no-op: the count went up and the shelf stayed empty. Say where the
              rows went and offer the one click that gets there. The count is
              everything waiting, which can exceed what this batch added. */}
                {result.unsorted_entries > 0 && (
                  <p className="mt-2 text-muted-foreground">
                    {result.unsorted_entries}{" "}
                    {result.unsorted_entries === 1 ? "entry is" : "entries are"}{" "}
                    waiting in Triage. Your library hides unsorted entries until
                    you sort them, so this is where the import went.{" "}
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
            {result && !undoResult && !pending && (
              <div className="mt-5 rounded-xl border border-border bg-surface p-4">
                <p className="text-sm text-muted-foreground">
                  You can undo this import for 24 hours after commit. The undo
                  reverses only fields that still match the imported values —
                  your later edits are preserved.
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
                className="mt-5 rounded-xl border border-border bg-surface p-4"
                role="status"
              >
                <h2 className="text-lg font-semibold">Import undone</h2>
                <p className="mt-1 text-sm text-foreground">
                  {undoResult.reverted}{" "}
                  {undoResult.reverted === 1 ? "change" : "changes"} reverted
                  {undoResult.retained > 0 &&
                    ` · ${undoResult.retained} retained (edited after import)`}
                </p>
                <BackToLibrary className="mt-3" />
              </div>
            )}
          </main>
        </Tabs>
      </TabsContent>
      <TabsContent value={TRIAGE_TAB} className="mt-0">
        <TriagePage />
      </TabsContent>
      <TabsContent value={EXPORT_TAB} className="mt-0">
        <ExportPanel />
      </TabsContent>
    </Tabs>
  );
}
