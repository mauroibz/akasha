import type { BundleMember } from "@/features/import/bundle";

export interface ImportRecord {
  record_id: number;
  row_number: number;
  title: string;
  creators: string[];
  suggested_status: string | null;
  score: number | null;
  score_provisional: boolean;
  shelves: string[];
  errors: Array<{ field: string; code: string; value?: string }>;
  planned_action: string;
  match_kind: string;
  candidates: number[];
  item: {
    title: string;
    subtitle: string | null;
    year: number | null;
    identifiers: Record<string, string>;
    metadata: Record<string, unknown>;
    creator_sort: string | null;
  };
  entry: {
    score: number | null;
    notes: string | null;
    date_added: string | null;
    values: Record<string, unknown>;
    score_provisional: boolean;
    suggested_status: string | null;
  };
  source_fields: Record<string, unknown>;
  cover_staged?: boolean;
}
export interface ImportInputSpec {
  kind: "upload" | "path" | "directory";
  label: string;
  field: string;
  accept: string | null;
  placeholder: string | null;
  help: string | null;
  /** How to obtain the source, one step per string, rendered in order. */
  guide: string[];
  /** What the input says while nothing has been chosen. */
  empty_state: string | null;
  help_url: string | null;
  browsable: boolean;
  /** Whether the connector can say what is worth uploading before it is sent. */
  incremental: boolean;
  accepts_files: boolean;
  max_bytes: number | null;
  max_files: number | null;
  /** A second way into the same connector, rendered beneath the primary. One deep. */
  alternate: ImportInputSpec | null;
}

export interface ImporterDefinition {
  id: string;
  label: string;
  /**
   * Every library this connector can fill, ordered, first-declared first.
   *
   * A list rather than one name because a television export carries films and shows
   * in one file (DEC-106). One entry means no choice to offer, so the screen renders
   * no target checkboxes at all.
   */
  item_types: string[];
  input: ImportInputSpec;
  /** Per-file ceiling for attachments created by an import. */
  attachment_max_bytes: number;
}

/** One level of a browsable connector's source. Relative names, never host paths. */
export interface ImportBrowseListing {
  path: string;
  parent: string | null;
  directories: string[];
  importable: boolean;
}

/**
 * A refused import request, carrying what the reader can do about it.
 *
 * The connector owns the sentence: it knows that a locked Calibre database means
 * "close Calibre and try again", and the shared screen cannot (DEC-080).
 */
export class ImportRequestError extends Error {
  readonly code: string;
  readonly action: string | null;

  constructor(message: string, code: string, action: string | null) {
    super(message);
    this.name = "ImportRequestError";
    this.code = code;
    this.action = action;
  }
}
export interface ImportPreview {
  batch_id: string;
  fingerprint: string;
  state: string;
  summary: {
    total: number;
    ready: number;
    errors: number;
    ambiguous: number;
    /** Rows for a library that was not ticked. Not an error — a choice. */
    skipped_not_requested: number;
    /** Rows of a kind no library holds, counted so they are never silent. */
    skipped_unsupported: number;
    skipped_reasons: Array<{ reason: string; count: number }>;
  };
  records: ImportRecord[];
}
export interface ImportResult {
  batch_id: string;
  state: string;
  created_items: number;
  created_entries: number;
  unchanged_entries: number;
  /** Everything waiting in triage after the commit, not only the rows it created. */
  unsorted_entries: number;
}
export interface JobProgress {
  id: string;
  batch_id: string | null;
  kind: string;
  state: string;
  progress: Record<string, unknown>;
  error: string | null;
  attempts: number;
  created_at: string;
  finished_at: string | null;
}
export interface UndoResult {
  batch_id: string;
  state: string;
  reverted: number;
  retained: number;
  skipped: number;
  reverted_entries: number;
  reverted_items: number;
  retained_items: number;
}

async function responseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const value = (await response.json().catch(() => null)) as {
      error?: {
        code?: string;
        message?: string;
        user_message?: string;
        action?: string;
      };
    } | null;
    const error = value?.error;
    // `user_message` is written for a person and `message` for a log; prefer the
    // first when the connector supplied one.
    throw new ImportRequestError(
      error?.user_message ?? error?.message ?? "Import request failed",
      error?.code ?? "import_failed",
      error?.action ?? null,
    );
  }
  return response.json() as Promise<T>;
}

export function getImporters() {
  return fetch("/api/importers").then((response) =>
    responseJson<ImporterDefinition[]>(response),
  );
}

export function browseImportSource(importerId: string, path: string) {
  return fetch(
    `/api/import/${encodeURIComponent(importerId)}/browse?path=${encodeURIComponent(path)}`,
  ).then((response) => responseJson<ImportBrowseListing>(response));
}

/**
 * Preview a source through whichever of the connector's inputs it belongs to.
 *
 * A connector may declare two (DEC-081), and the request itself says which is in
 * use: a body of parts is the file or folder input, a JSON body is the path one.
 * `spec` is the input the screen actually collected, not necessarily the primary.
 */
/** Which of the offered members the server actually wants (DEC-082). */
export interface ImportPlanResult {
  wanted: string[];
  holding: number;
  reason: string | null;
}

/**
 * Ask before sending.
 *
 * The cheap half of the source goes up with a manifest of what is being held back,
 * and the server answers with the subset worth uploading. It answers rather than the
 * client hashing because `crypto.subtle` is undefined on a plain-HTTP LAN origin,
 * which is how this application is actually served.
 */
export function planImport(
  importer: ImporterDefinition,
  spec: ImportInputSpec,
  cheap: BundleMember[],
  candidates: BundleMember[],
) {
  const form = new FormData();
  for (const member of cheap) form.append(spec.field, member.file, member.path);
  form.append(
    "manifest",
    JSON.stringify(
      candidates.map((member) => ({
        path: member.path,
        size: member.file.size,
      })),
    ),
  );
  return fetch(`/api/import/${encodeURIComponent(importer.id)}/plan`, {
    method: "POST",
    body: form,
  }).then((response) => responseJson<ImportPlanResult>(response));
}

/**
 * Preview a source into the libraries that were chosen for it.
 *
 * `targets` is which of the connector\'s declared types this import is for, omitted
 * when every one is wanted. It travels as one comma-separated field so an upload and
 * a folder bundle say it the same way, and as a list in the JSON path body. The
 * server, not this client, applies it (DEC-106): a filter applied here would have to
 * be reimplemented, correctly, by every future caller.
 */
export function previewImport(
  importer: ImporterDefinition,
  spec: ImportInputSpec,
  source: File | string | BundleMember[],
  targets?: string[],
) {
  const url = `/api/import/${encodeURIComponent(importer.id)}/preview`;
  const chosen =
    targets && targets.length < importer.item_types.length ? targets : null;
  if (spec.kind === "directory") {
    const form = new FormData();
    for (const member of source as BundleMember[]) {
      // The relative path travels as the part filename; the server validates it
      // and refuses anything outside the shape it asked for.
      form.append(spec.field, member.file, member.path);
    }
    if (chosen) form.append("targets", chosen.join(","));
    return fetch(url, { method: "POST", body: form }).then((response) =>
      responseJson<ImportPreview>(response),
    );
  }
  if (spec.kind === "upload") {
    const form = new FormData();
    form.append(spec.field, source as File);
    if (chosen) form.append("targets", chosen.join(","));
    return fetch(url, { method: "POST", body: form }).then((response) =>
      responseJson<ImportPreview>(response),
    );
  }
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      [spec.field]: source,
      ...(chosen ? { targets: chosen } : {}),
    }),
  }).then((response) => responseJson<ImportPreview>(response));
}

export function commitImport(
  importerId: string,
  batchId: string,
  choices: Array<{ record_id: number; item_id: number | null }>,
) {
  return fetch(`/api/import/${encodeURIComponent(importerId)}/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ batch_id: batchId, choices }),
  }).then((response) => responseJson<ImportResult>(response));
}

export interface ImportFileResult {
  id: number;
  item_id: number;
  filename: string;
  byte_size: number;
  sha256: string;
}

/** Attach one planned source member after its batch has committed. */
export function uploadImportFile(
  importerId: string,
  batchId: string,
  member: BundleMember,
) {
  const form = new FormData();
  form.append("path", member.path);
  form.append("file", member.file, member.path);
  return fetch(
    `/api/import/${encodeURIComponent(importerId)}/batches/${encodeURIComponent(batchId)}/files`,
    { method: "POST", body: form },
  ).then((response) => responseJson<ImportFileResult>(response));
}

export function getJobProgress(jobId: string) {
  return fetch(`/api/import/jobs/${jobId}`).then((response) =>
    responseJson<JobProgress>(response),
  );
}

export function undoBatch(batchId: string) {
  return fetch(`/api/import/batches/${batchId}`, {
    method: "DELETE",
  }).then((response) => responseJson<UndoResult>(response));
}
