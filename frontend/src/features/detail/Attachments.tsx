import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { toast } from "sonner";

import {
  attachmentHref,
  deleteAttachment,
  fetchAttachments,
  uploadAttachment,
} from "@/api/library";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/bytes";

/**
 * Files attached to this edition.
 *
 * Its own query rather than part of the entry payload, so a slow or failed read
 * of this list never delays the page it sits on — the sprint's requirement that
 * the surface must not block what it lives on. The download is a plain anchor
 * because the server answers with `Content-Disposition: attachment`, so the
 * browser saves it and no script has to touch the bytes.
 */
export function Attachments({ itemId }: { itemId: number }) {
  const cache = useQueryClient();
  const picker = useRef<HTMLInputElement>(null);
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
    <section aria-labelledby="attachments-heading" data-testid="attachments">
      <div className="flex items-center justify-between gap-4">
        <h2 id="attachments-heading" className="text-sm font-medium">
          Files
        </h2>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => picker.current?.click()}
          disabled={upload.isPending}
        >
          {upload.isPending ? "Attaching…" : "Attach a file"}
        </Button>
        <input
          ref={picker}
          type="file"
          className="sr-only"
          aria-label="Attach a file"
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
          {attachments.map((attachment) => (
            <li
              key={attachment.id}
              className="flex items-center justify-between gap-4 text-sm"
            >
              <a
                href={attachmentHref(itemId, attachment.id)}
                className="truncate underline underline-offset-4"
                download
              >
                {attachment.filename}
              </a>
              <span className="shrink-0 text-xs text-muted-foreground">
                {formatBytes(attachment.byte_size)}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Remove ${attachment.filename}`}
                onClick={() => remove.mutate(attachment.id)}
                disabled={remove.isPending}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
