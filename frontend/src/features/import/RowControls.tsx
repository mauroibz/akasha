import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { excludeRow, includeRow, researchRow } from "@/api/imports";
import { Button } from "@/components/ui/button";

/**
 * The per-row way out of the import entirely (the owner's 2026-09-14
 * decision): "Don't import this row" excludes the row from the commit, the
 * summary recounts, and the control becomes its own undo.
 */
export function RowExcludeControl({
  recordId,
  excluded,
  batchId,
  importerId,
  onChanged,
}: {
  recordId: number;
  excluded: boolean;
  batchId: string;
  importerId: string;
  onChanged: () => void;
}) {
  const mutation = useMutation({
    mutationFn: () =>
      excluded
        ? includeRow(importerId, batchId, recordId)
        : excludeRow(importerId, batchId, recordId),
    onSuccess: () => {
      onChanged();
    },
    onError: () => {
      toast.error("That change could not be saved", {
        description: "The row was not changed.",
      });
    },
  });

  return (
    <Button
      variant={excluded ? "ghost" : "outline"}
      size="sm"
      className="shrink-0 rounded-full text-xs"
      disabled={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      {excluded ? "Import this row after all" : "Don't import this row"}
    </Button>
  );
}

/**
 * The edit-and-search form shared by the proposal list and the no-result
 * row: pre-fills with the row's current text and submits the re-search (the
 * owner's 2026-09-14 decision — available on any row, because a bad query
 * can also produce wrong proposals). The spreadsheet's own cells stay
 * untouched in `source_fields`.
 */
export function ResearchForm({
  recordId,
  batchId,
  importerId,
  initialTitle,
  initialAuthor,
  onSearched,
  onCancel,
}: {
  recordId: number;
  batchId: string;
  importerId: string;
  initialTitle: string;
  initialAuthor: string;
  onSearched: () => void;
  onCancel: () => void;
}) {
  const [draftTitle, setDraftTitle] = useState(initialTitle);
  const [draftAuthor, setDraftAuthor] = useState(initialAuthor);

  const research = useMutation({
    mutationFn: () =>
      researchRow(importerId, batchId, recordId, {
        title: draftTitle,
        author: draftAuthor,
      }),
    onSuccess: () => {
      toast.success("Searched again", {
        description: "The row now carries the edited text and fresh results.",
      });
      onSearched();
    },
    onError: () => {
      toast.error("The search could not run", {
        description: "The row was not changed.",
      });
    },
  });

  return (
    <form
      className="space-y-2 rounded-xl border border-border bg-surface p-3"
      onSubmit={(event) => {
        event.preventDefault();
        research.mutate();
      }}
    >
      <label className="block">
        <span className="text-sm text-muted-foreground">Title</span>
        <input
          className="mt-1 h-11 w-full rounded-md border border-input bg-transparent px-3 text-base focus-ring"
          value={draftTitle}
          onChange={(event) => setDraftTitle(event.target.value)}
          autoFocus
        />
      </label>
      <label className="block">
        <span className="text-sm text-muted-foreground">Author</span>
        <input
          className="mt-1 h-11 w-full rounded-md border border-input bg-transparent px-3 text-base focus-ring"
          value={draftAuthor}
          onChange={(event) => setDraftAuthor(event.target.value)}
        />
      </label>
      <div className="flex gap-2">
        <Button
          size="sm"
          className="rounded-full"
          type="submit"
          disabled={research.isPending || !draftTitle.trim()}
        >
          {research.isPending ? "Searching…" : "Search again"}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          className="rounded-full"
          type="button"
          onClick={onCancel}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}

/**
 * A row whose search finished with nothing to offer: the honest empty state
 * plus the affordance that makes it actionable — the edit-and-search form
 * (fix the text; the providers answered the question it was asked). The
 * exclusion control lives on the row header, next to the title.
 */
export function NoResultRow({
  recordId,
  title,
  author,
  batchId,
  importerId,
  onAnswered,
}: {
  recordId: number;
  title: string;
  author: string;
  batchId: string;
  importerId: string;
  onAnswered: () => void;
}) {
  const [editing, setEditing] = useState(false);

  return (
    <div className="mt-3 space-y-2">
      <p className="rounded-xl border border-dashed border-border p-3 text-sm text-muted-foreground">
        No results. Fix the text and search again, or keep the row as you typed
        it.
      </p>
      {editing ? (
        <ResearchForm
          recordId={recordId}
          batchId={batchId}
          importerId={importerId}
          initialTitle={title}
          initialAuthor={author}
          onSearched={() => {
            setEditing(false);
            onAnswered();
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <Button
          variant="ghost"
          size="sm"
          className="rounded-full text-xs"
          onClick={() => setEditing(true)}
        >
          Wrong text? Edit and search again
        </Button>
      )}
    </div>
  );
}
