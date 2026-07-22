export interface ImportRecord {
  record_id: number;
  row_number: number;
  goodreads_book_id: string;
  title: string;
  authors: string[];
  isbn: string | null;
  suggested_status: string | null;
  score: number | null;
  score_provisional: boolean;
  shelves: string[];
  errors: Array<{ field: string; code: string; value?: string }>;
  planned_action: string;
  match_kind: string;
  candidates: number[];
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
