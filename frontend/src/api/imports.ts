export interface ImportRecord {
  record_id: number;
  row_number: number;
  goodreads_book_id?: string | null;
  calibre_book_id?: string | null;
  calibre_uuid?: string | null;
  title: string;
  creators: string[];
  isbn: string | null;
  suggested_status: string | null;
  score: number | null;
  score_provisional: boolean;
  shelves: string[];
  errors: Array<{ field: string; code: string; value?: string }>;
  planned_action: string;
  match_kind: string;
  candidates: number[];
  cover_staged?: boolean;
}
export interface ImportPreview {
  batch_id: string;
  fingerprint: string;
  state: string;
  summary: { total: number; ready: number; errors: number; ambiguous: number };
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
      error?: { message?: string };
    } | null;
    throw new Error(value?.error?.message ?? "Import request failed");
  }
  return response.json() as Promise<T>;
}

export function previewGoodreads(file: File) {
  const form = new FormData();
  form.append("file", file);
  return fetch("/api/import/goodreads/preview", {
    method: "POST",
    body: form,
  }).then((response) => responseJson<ImportPreview>(response));
}

export function commitGoodreads(
  batchId: string,
  choices: Array<{ record_id: number; item_id: number | null }>,
) {
  return fetch("/api/import/goodreads/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ batch_id: batchId, choices }),
  }).then((response) => responseJson<ImportResult>(response));
}

export function previewCalibre(libraryPath: string) {
  return fetch("/api/import/calibre/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ library_path: libraryPath }),
  }).then((response) => responseJson<ImportPreview>(response));
}

export function commitCalibre(
  batchId: string,
  choices: Array<{ record_id: number; item_id: number | null }>,
) {
  return fetch("/api/import/calibre/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ batch_id: batchId, choices }),
  }).then((response) => responseJson<ImportResult>(response));
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
