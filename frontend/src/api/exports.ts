import { ImportRequestError, responseJson } from "@/api/imports";

/**
 * One declared export view, shaped like `ImporterDefinition` pointed the other way
 * (Sprint 068's `ExportViewResponse`, DEC-080's pattern): the screen renders this
 * without knowing which view or which domain it is holding.
 */
export interface ExportViewDefinition {
  id: string;
  label: string;
  item_types: string[];
  media_type: string;
  lossless: boolean;
  guide: string[];
  help_url: string | null;
  carries: string[];
  /** How many entries this view would write for the library as it stands. */
  count: number;
}

export function getExports() {
  return fetch("/api/exports").then((response) =>
    responseJson<ExportViewDefinition[]>(response),
  );
}

/** Where one view's file, for one domain it carries, is downloaded from. */
export function exportViewUrl(view: ExportViewDefinition, itemType: string) {
  return `/api/export/${encodeURIComponent(view.id)}?type=${encodeURIComponent(itemType)}`;
}

/**
 * The lossless path (Sprint 068 finding 6): every domain, one file, nothing dropped.
 *
 * Not a registered view — `GET /api/exports` never lists it, so this screen is the
 * one place it is named, ahead of every declared row (proposal §2.5 deliverable 7).
 */
export const LOSSLESS_EXPORT_URL = "/api/export";

/** The filename the server chose, read back from the header it set for the download. */
function filenameFrom(response: Response): string {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  return /filename="([^"]+)"/.exec(disposition)?.[1] ?? "akasha-export";
}

/**
 * Fetch a streamed export and hand it to the browser's own download mechanism.
 *
 * `fetch` rather than a plain `<a href>` link: a link gives no way to catch a failed
 * request or to know when the file has actually arrived, and Sprint 069 requires both
 * (AC4). The object URL is revoked once the browser has taken the click.
 */
export async function downloadExport(url: string): Promise<void> {
  const response = await fetch(url);
  if (!response.ok) {
    const value = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string; user_message?: string };
    } | null;
    const error = value?.error;
    throw new ImportRequestError(
      error?.user_message ??
        error?.message ??
        "The file could not be downloaded.",
      error?.code ?? "export_failed",
      null,
    );
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filenameFrom(response);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
