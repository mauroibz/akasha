import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { toast } from "sonner";

import type { Attachment } from "@/api/library";
import {
  attachmentHref,
  deleteAttachment,
  fetchAttachments,
  renameAttachment,
  uploadAttachment,
} from "@/api/library";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Input } from "@/components/ui/input";
import { formatBytes } from "@/lib/bytes";
import { cn } from "@/lib/utils";

/**
 * Files attached to this edition.
 *
 * Its own query rather than part of the entry payload, so a slow or failed read
 * of this list never delays the page it sits on — the sprint's requirement that
 * the surface must not block what it lives on. The download is a plain anchor
 * because the server answers with `Content-Disposition: attachment`, so the
 * browser saves it and no script has to touch the bytes.
 *
 * Renaming is inline rather than a modal, matching how the rest of the app edits
 * (product spec §7: dialogs are for deletes, not for edits).
 *
 * The frame is the page's, not this component's: the detail page wraps it in the
 * labelled region that makes it a peer of the personal and edition panels, so this
 * renders its heading and its list and nothing about where it sits.
 */
export function Attachments({ itemId }: { itemId: number }) {
  const cache = useQueryClient();
  const picker = useRef<HTMLInputElement>(null);
  const [renaming, setRenaming] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [confirming, setConfirming] = useState<Attachment | null>(null);
  const key = ["attachments", itemId];

  const { data, isPending, isError } = useQuery({
    queryKey: key,
    queryFn: () => fetchAttachments(itemId),
  });

  const upload = useMutation({
    mutationFn: (file: File) => uploadAttachment(itemId, file),
    onSuccess: (added) => {
      void cache.invalidateQueries({ queryKey: key });
      toast.success(`Attached ${added.filename}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const rename = useMutation({
    mutationFn: ({ id, filename }: { id: number; filename: string }) =>
      renameAttachment(itemId, id, filename),
    onSuccess: (renamed) => {
      void cache.invalidateQueries({ queryKey: key });
      setRenaming(null);
      toast.success(`Renamed to ${renamed.filename}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (attachmentId: number) =>
      deleteAttachment(itemId, attachmentId),
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: key });
      toast.success("File removed");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const attachments = data ?? [];

  return (
    <div data-testid="attachments">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-primary">
          Files
        </h2>
        <Button
          type="button"
          className="rounded-full px-5"
          onClick={() => picker.current?.click()}
          disabled={upload.isPending}
        >
          {upload.isPending ? "Attaching…" : "Attach a file"}
        </Button>
        <input
          ref={picker}
          type="file"
          className="sr-only"
          data-testid="attachment-picker"
          // Out of the accessibility tree entirely, not merely out of view. The
          // button above is the control: it opens this picker and carries the
          // name. Leaving this exposed published a second "Attach a file" with
          // its own tab stop, so the same action appeared twice with nothing to
          // tell them apart. Not focusable, so hiding it strands no one.
          aria-hidden="true"
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Cleared so choosing the same file twice still fires a change.
            event.target.value = "";
            if (file) upload.mutate(file);
          }}
        />
      </div>

      {isPending ? (
        <p className="mt-2 text-sm text-muted-foreground">Loading files…</p>
      ) : isError ? (
        <p className="mt-2 text-sm text-muted-foreground">
          Files could not be loaded.
        </p>
      ) : attachments.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          No files attached yet.
        </p>
      ) : (
        <ul className="mt-2 space-y-1">
          {attachments.map((attachment) => {
            const renamingThis = renaming === attachment.id;
            // Per row: one file being worked on must not disable the controls
            // on every other row.
            const renamePending =
              rename.isPending && rename.variables?.id === attachment.id;
            const removePending =
              remove.isPending && remove.variables === attachment.id;

            return (
              <li
                key={attachment.id}
                className="flex items-center gap-2 text-sm"
              >
                {renamingThis ? (
                  <form
                    className="flex flex-1 items-center gap-2"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const filename = draft.trim();
                      if (!filename || filename === attachment.filename) {
                        setRenaming(null);
                        return;
                      }
                      rename.mutate({ id: attachment.id, filename });
                    }}
                  >
                    <Input
                      autoFocus
                      value={draft}
                      aria-label={`New name for ${attachment.filename}`}
                      className="h-8 flex-1"
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") setRenaming(null);
                      }}
                    />
                    <Button
                      type="submit"
                      variant="outline"
                      size="sm"
                      disabled={renamePending}
                    >
                      {renamePending ? "Saving…" : "Save"}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setRenaming(null)}
                    >
                      Cancel
                    </Button>
                  </form>
                ) : (
                  <>
                    <a
                      href={attachmentHref(itemId, attachment.id)}
                      className="min-w-0 flex-1 truncate underline underline-offset-4"
                      download
                    >
                      {attachment.filename}
                    </a>
                    {/* Fixed width so size and actions line up down the list
                        rather than tracking each filename's length. */}
                    <span className="w-16 shrink-0 text-right text-xs text-muted-foreground">
                      {formatBytes(attachment.byte_size)}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`Rename ${attachment.filename}`}
                      onClick={() => {
                        setDraft(attachment.filename);
                        setRenaming(attachment.id);
                      }}
                    >
                      Rename
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove ${attachment.filename}`}
                      onClick={() => setConfirming(attachment)}
                      disabled={removePending}
                    >
                      Remove
                    </Button>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <AlertDialog
        open={confirming !== null}
        onOpenChange={(open) => {
          if (!open) setConfirming(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this file?</AlertDialogTitle>
            <AlertDialogDescription>
              {confirming?.filename} will be detached from this edition. If no
              other edition has the same file, the upload is deleted and cannot
              be recovered except from a backup.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(
                buttonVariants({ variant: "destructive" }),
                "rounded-full px-5",
              )}
              onClick={() => {
                if (confirming) remove.mutate(confirming.id);
                setConfirming(null);
              }}
            >
              Remove file
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
