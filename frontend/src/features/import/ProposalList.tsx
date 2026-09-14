import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  answerProposal,
  researchRow,
  type ImportProposal,
} from "@/api/imports";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * How many proposals a row shows before its "Show more" unfolds the rest.
 * Ten are stored per row (the owner's 2026-09-14 feedback); three render by
 * default so a healthy row stays scannable, and the deeper answers — where a
 * badly-ranked Spanish title or a common-word query lands — are one click
 * away rather than a re-search.
 */
const COLLAPSED = 3;

/**
 * One proposal, as the row's confirm step offers it. The provider's own name
 * for itself (`openlibrary`, `googlebooks`) is shown verbatim: it is the
 * source's identity in the ledger, and dressing it up ("Open Library") would
 * be copy this screen does not own.
 */
function providerLabel(source: string): string {
  return source;
}

function ProposalCard({
  proposal,
  recordId,
  batchId,
  importerId,
  disabled,
  onAnswered,
}: {
  proposal: ImportProposal;
  recordId: number;
  batchId: string;
  importerId: string;
  disabled: boolean;
  onAnswered: () => void;
}) {
  const answer = useMutation({
    mutationFn: (
      choice: { source: string; source_id: string } | { discard: true },
    ) => answerProposal(importerId, batchId, recordId, choice),
    onSuccess: () => {
      onAnswered();
    },
    onError: () => {
      toast.error("That answer could not be saved", {
        description: "The row was not changed.",
      });
    },
  });

  const payload = proposal.payload;
  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-xl border p-3",
        proposal.chosen === true
          ? "border-primary bg-primary/5"
          : proposal.chosen === false
            ? "border-border opacity-60"
            : "border-border bg-surface",
      )}
    >
      <CoverImage
        src={payload.cover_url}
        alt=""
        className="h-20 w-14 shrink-0 rounded-md"
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{payload.title}</p>
        <p className="truncate text-xs text-muted-foreground">
          {payload.creators.join(", ") || "Creator unknown"}
        </p>
        <p className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
          {payload.year != null && <span>{payload.year}</span>}
          {payload.language && (
            <>
              <span aria-hidden="true">·</span>
              <span>{payload.language}</span>
            </>
          )}
          <span aria-hidden="true">·</span>
          <span>{providerLabel(proposal.source)}</span>
        </p>
      </div>
      <div className="flex shrink-0 flex-col gap-2">
        {proposal.chosen === true ? (
          <span className="rounded-full border border-primary px-3 py-1 text-xs text-primary">
            Confirmed
          </span>
        ) : (
          <Button
            size="sm"
            className="rounded-full"
            disabled={disabled || answer.isPending}
            onClick={() =>
              answer.mutate({
                source: proposal.source,
                source_id: proposal.source_id,
              })
            }
          >
            Confirm
          </Button>
        )}
      </div>
    </li>
  );
}

/**
 * The editable title/author and its "Search again" trigger — on every row,
 * not only empty ones (the owner's 2026-09-14 decision: a bad query can also
 * produce wrong proposals). Pre-fills with the row's current text; the
 * spreadsheet's own cells stay untouched in `source_fields`.
 */
function SearchAgain({
  title,
  author,
  recordId,
  batchId,
  importerId,
  disabled,
  onAnswered,
}: {
  title: string;
  author: string;
  recordId: number;
  batchId: string;
  importerId: string;
  disabled: boolean;
  onAnswered: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(title);
  const [draftAuthor, setDraftAuthor] = useState(author);

  const research = useMutation({
    mutationFn: () =>
      researchRow(importerId, batchId, recordId, {
        title: draftTitle,
        author: draftAuthor,
      }),
    onSuccess: () => {
      setEditing(false);
      toast.success("Searched again", {
        description: "The row now carries the edited text and fresh results.",
      });
      onAnswered();
    },
    onError: () => {
      toast.error("The search could not run", {
        description: "The row was not changed.",
      });
    },
  });

  if (disabled && !editing) return null;
  return (
    <div className="space-y-2">
      {editing && (
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
              onClick={() => setEditing(false)}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
      {!editing && (
        <Button
          variant="ghost"
          size="sm"
          className="rounded-full text-xs"
          disabled={disabled}
          onClick={() => {
            setDraftTitle(title);
            setDraftAuthor(author);
            setEditing(true);
          }}
        >
          Wrong text? Edit and search again
        </Button>
      )}
    </div>
  );
}

/**
 * The proposals the background search found for one row, ranked, with the
 * owner's answer per result: confirm one, or discard the lot and keep the row
 * exactly as the spreadsheet typed it (Sprint 083 D4.2).
 *
 * While the batch is still `matching` the controls are disabled — the job may
 * still rewrite this record's proposals, and answering it mid-flight would be
 * answering a question that is still being asked.
 *
 * The 2026-09-14 owner feedback adds two affordances: "Show more" unfolds the
 * stored ten past the first three, and an editable title/author with a
 * "Search again" button on every row.
 */
export function ProposalList({
  recordId,
  title,
  author,
  proposals,
  batchId,
  importerId,
  matching,
  onAnswered,
}: {
  recordId: number;
  title: string;
  author: string;
  proposals: ImportProposal[];
  batchId: string;
  importerId: string;
  matching: boolean;
  onAnswered: () => void;
}) {
  const discard = useMutation({
    mutationFn: () =>
      answerProposal(importerId, batchId, recordId, { discard: true }),
    onSuccess: () => {
      toast.success(`Kept "${title}" as you typed it`, {
        description: "None of the proposals will be used.",
      });
      onAnswered();
    },
    onError: () => {
      toast.error("That answer could not be saved", {
        description: "The row was not changed.",
      });
    },
  });

  const [expanded, setExpanded] = useState(false);

  const answered = proposals.some(
    (proposal) => proposal.chosen === true || proposal.chosen === false,
  );
  const shown = expanded ? proposals : proposals.slice(0, COLLAPSED);
  const hidden = proposals.length - shown.length;

  if (proposals.length === 0) {
    return (
      <div className="mt-3 space-y-2">
        <p className="rounded-xl border border-dashed border-border p-3 text-sm text-muted-foreground">
          {matching
            ? "Searching…"
            : "No results. Fix the text and search again, or keep the row as you typed it."}
        </p>
        <SearchAgain
          title={title}
          author={author}
          recordId={recordId}
          batchId={batchId}
          importerId={importerId}
          disabled={matching}
          onAnswered={onAnswered}
        />
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs text-muted-foreground">
        {answered ? "Your answer:" : "Is one of these the book?"}
      </p>
      <ul className="space-y-2">
        {shown.map((proposal) => (
          <ProposalCard
            key={`${proposal.source}-${proposal.source_id}`}
            proposal={proposal}
            recordId={recordId}
            batchId={batchId}
            importerId={importerId}
            disabled={matching}
            onAnswered={onAnswered}
          />
        ))}
      </ul>
      {!expanded && hidden > 0 && (
        <Button
          variant="ghost"
          size="sm"
          className="rounded-full text-xs"
          onClick={() => setExpanded(true)}
        >
          Show more ({hidden})
        </Button>
      )}
      {expanded && proposals.length > COLLAPSED && (
        <Button
          variant="ghost"
          size="sm"
          className="rounded-full text-xs"
          onClick={() => setExpanded(false)}
        >
          Show fewer
        </Button>
      )}
      <SearchAgain
        title={title}
        author={author}
        recordId={recordId}
        batchId={batchId}
        importerId={importerId}
        disabled={matching}
        onAnswered={onAnswered}
      />
      {answered ? (
        <Button
          variant="ghost"
          size="sm"
          className="rounded-full text-xs"
          disabled={matching || discard.isPending}
          onClick={() => discard.mutate()}
        >
          Undo my answer
        </Button>
      ) : (
        // The row's own way out: none of these is the book, and the row stays
        // exactly as the spreadsheet typed it (D4.2's Discard).
        <Button
          variant="outline"
          size="sm"
          className="rounded-full text-xs"
          disabled={matching || discard.isPending}
          onClick={() => discard.mutate()}
        >
          None of these — keep as typed
        </Button>
      )}
    </div>
  );
}
