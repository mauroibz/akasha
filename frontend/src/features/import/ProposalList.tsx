import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { answerProposal, type ImportProposal } from "@/api/imports";
import { CoverImage } from "@/components/CoverImage";
import { Button } from "@/components/ui/button";
import { ResearchForm } from "@/features/import/RowControls";
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
 * The proposals the background search found for one row, ranked, with the
 * owner's answer per result: confirm one, or discard the lot and keep the row
 * exactly as the spreadsheet typed it (Sprint 083 D4.2).
 *
 * While the batch is still `matching` the controls are disabled — the job may
 * still rewrite this record's proposals, and answering it mid-flight would be
 * answering a question that is still being asked.
 *
 * The 2026-09-14 owner feedback shapes the action area: the secondary
 * actions — Show more, the edit-and-re-search trigger, the discard — sit side
 * by side in one wrapping row under the proposals (one line to scan, the same
 * height for every row), and the edit form opens above them, pushing nothing
 * sideways.
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
  const [editing, setEditing] = useState(false);

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
      {editing && (
        <ResearchForm
          recordId={recordId}
          batchId={batchId}
          importerId={importerId}
          initialTitle={title}
          initialAuthor={author}
          onSearched={() => {
            setEditing(false);
            setExpanded(false);
            onAnswered();
          }}
          onCancel={() => setEditing(false)}
        />
      )}
      {/* The row's secondary actions, side by side in one wrapping row:
          the fold, the correction, and the way out read as peers of one
          decision about this row, not a paragraph of buttons. */}
      <div className="flex flex-wrap items-center gap-2">
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
        {!editing && (
          <Button
            variant="ghost"
            size="sm"
            className="rounded-full text-xs"
            disabled={matching}
            onClick={() => setEditing(true)}
          >
            Wrong text? Edit and search again
          </Button>
        )}
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
          // The row's own way out: none of these is the book, and the row
          // stays exactly as the spreadsheet typed it (D4.2's Discard).
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
    </div>
  );
}
