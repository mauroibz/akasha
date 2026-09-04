import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { DeclarationGuide } from "@/features/import/ConnectorGuide";
import { useItemTypes } from "@/features/library/useItemTypes";
import {
  downloadExport,
  exportViewUrl,
  getExports,
  LOSSLESS_EXPORT_URL,
  type ExportViewDefinition,
} from "@/api/exports";
import { ImportRequestError } from "@/api/imports";

/** One (view, domain) pair the screen can offer a download for. */
interface ExportRow {
  readonly key: string;
  readonly heading: string;
  readonly domainLabel: string;
  readonly carries: string[];
  readonly count: number;
  readonly guide: string[];
  readonly helpUrl: string | null;
  readonly url: string;
}

type DownloadState =
  | { readonly kind: "idle" }
  | { readonly kind: "working" }
  | { readonly kind: "done" }
  | { readonly kind: "failed"; readonly message: string };

/**
 * A row per (view, domain) the registry declares, generic over both.
 *
 * A view's `item_types` may name more than one domain (a future connector could,
 * the way a Cinemeta-backed importer already spans two); this screen renders one row
 * per pairing rather than one per view so a reader always downloads one domain's
 * file at a time, matching what `?type=` on `GET /api/export/{view}` requires.
 * Every registered view today declares exactly one domain, so this degenerates to
 * one row per view — the generality costs nothing and asks nothing of a future
 * multi-domain view beyond declaring itself (AC2).
 */
function rowsFrom(
  views: readonly ExportViewDefinition[],
  domainLabel: (itemType: string) => string,
): ExportRow[] {
  return views.flatMap((view) =>
    view.item_types.map((itemType) => ({
      key: `${view.id}-${itemType}`,
      heading:
        view.item_types.length > 1
          ? `${view.label} — ${domainLabel(itemType)}`
          : view.label,
      domainLabel: domainLabel(itemType),
      carries: view.carries,
      // A view's `count` is summed across every domain it carries (Sprint 068's
      // `GET /api/exports`), so a per-domain zero state is only exact while every
      // registered view carries a single domain — true of all six views this
      // sprint ships against. A future multi-domain view would need its own
      // per-domain count to keep deliverable 6 honest; none exists yet.
      count: view.count,
      guide: view.guide,
      helpUrl: view.help_url,
      url: exportViewUrl(view, itemType),
    })),
  );
}

function ExportRowPanel({
  row,
  state,
  onDownload,
}: {
  row: ExportRow;
  state: DownloadState;
  onDownload: () => void;
}) {
  const empty = row.count === 0;
  const guideHeadingId = `export-guide-${row.key}`;
  return (
    <article className="rounded-2xl bg-surface p-4" data-export-row={row.key}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold">{row.heading}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Carries {row.carries.join(", ")}.
          </p>
          <p className="mt-1 text-sm" role="status">
            {row.count} {row.count === 1 ? "entry" : "entries"}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <Button
            className="rounded-full px-5"
            disabled={empty || state.kind === "working"}
            onClick={onDownload}
          >
            {state.kind === "working" ? "Downloading…" : "Download"}
          </Button>
          {empty && (
            <p className="mt-1 text-xs text-muted-foreground">
              Nothing to export yet — add a {row.domainLabel.toLowerCase()}{" "}
              entry first.
            </p>
          )}
        </div>
      </div>
      {state.kind === "done" && (
        <p className="mt-2 text-sm text-score-top" role="status">
          Downloaded.
        </p>
      )}
      {state.kind === "failed" && (
        <p className="mt-2 text-sm text-destructive" role="alert">
          {state.message}
        </p>
      )}
      {row.guide.length > 0 && (
        <div className="mt-3">
          <DeclarationGuide
            headingId={guideHeadingId}
            heading={`Where this file goes`}
            guide={row.guide}
            helpUrl={row.helpUrl}
            helpLabel={`${row.domainLabel} import documentation`}
          />
        </div>
      )}
    </article>
  );
}

/**
 * The export tab (Sprint 069): a row per declared view, and nothing of its own.
 *
 * `GET /api/exports` names every registered view; this component adds exactly one
 * row it is not told about — the lossless JSON, which is not a registered view
 * (Sprint 068 kept `GET /api/export` outside the registry on purpose) and is placed
 * first and marked as such (deliverable 7). Everything else renders from the
 * declaration alone: no view's id, label or domain is named in this file's logic.
 */
export function ExportPanel() {
  const [views, setViews] = useState<ExportViewDefinition[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [downloads, setDownloads] = useState<Record<string, DownloadState>>({});
  const itemTypes = useItemTypes(true);

  useEffect(() => {
    void getExports()
      .then(setViews)
      .catch((reason: Error) =>
        setLoadError(
          reason instanceof ImportRequestError
            ? reason.message
            : "Could not load what can be exported.",
        ),
      );
  }, []);

  const domainLabel = (itemType: string) =>
    itemTypes.data?.find((type) => type.id === itemType)?.label ?? itemType;

  const totalEntries =
    views
      ?.filter((view) => view.id === "table")
      .reduce((sum, view) => sum + view.count, 0) ?? 0;

  const runDownload = (key: string, url: string) => {
    setDownloads((current) => ({ ...current, [key]: { kind: "working" } }));
    void downloadExport(url)
      .then(() =>
        setDownloads((current) => ({ ...current, [key]: { kind: "done" } })),
      )
      .catch((reason: Error) =>
        setDownloads((current) => ({
          ...current,
          [key]: {
            kind: "failed",
            message:
              reason instanceof ImportRequestError
                ? reason.message
                : "The file could not be downloaded.",
          },
        })),
      );
  };

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <h1 className="text-4xl font-semibold">Export</h1>
      <p className="mt-2 text-muted-foreground">
        Take your library elsewhere. Every file below is generated from your
        library as it stands right now.
      </p>
      {loadError && (
        <div className="mt-4 rounded-xl bg-destructive/10 p-4" role="alert">
          <p className="text-destructive">{loadError}</p>
        </div>
      )}
      {views && (
        <div className="mt-7 space-y-3">
          <article
            className="rounded-2xl bg-surface p-4"
            data-export-row="lossless"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="font-semibold">
                  Full library backup (JSON) — nothing lost
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Every entry, every domain, in the one format that can
                  reconstruct your library exactly: identifiers, attachments and
                  exact scores included. This is the file to keep.
                </p>
                <p className="mt-1 text-sm" role="status">
                  {totalEntries} {totalEntries === 1 ? "entry" : "entries"}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <Button
                  className="rounded-full px-5"
                  disabled={
                    totalEntries === 0 || downloads.lossless?.kind === "working"
                  }
                  onClick={() => runDownload("lossless", LOSSLESS_EXPORT_URL)}
                >
                  {downloads.lossless?.kind === "working"
                    ? "Downloading…"
                    : "Download"}
                </Button>
                {totalEntries === 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Nothing to export yet.
                  </p>
                )}
              </div>
            </div>
            {downloads.lossless?.kind === "done" && (
              <p className="mt-2 text-sm text-score-top" role="status">
                Downloaded.
              </p>
            )}
            {downloads.lossless?.kind === "failed" && (
              <p className="mt-2 text-sm text-destructive" role="alert">
                {downloads.lossless.message}
              </p>
            )}
          </article>
          {rowsFrom(views, domainLabel).map((row) => (
            <ExportRowPanel
              key={row.key}
              row={row}
              state={downloads[row.key] ?? { kind: "idle" }}
              onDownload={() => runDownload(row.key, row.url)}
            />
          ))}
        </div>
      )}
    </main>
  );
}
