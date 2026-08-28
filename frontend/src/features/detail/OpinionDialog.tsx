import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import type { LibraryEntry } from "@/api/library";
import { ScorePicker } from "@/components/ScorePicker";
import { StatusSelect } from "@/components/StatusSelect";
import {
  entryFieldLabel,
  formatsFor,
  hasEntryField,
  progressFor,
  statusesFor,
} from "@/features/library/labels";
import type { EntryFieldName } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { FormatPicker } from "@/features/library/FormatPicker";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "./Field";
import { opinionSchema, type OpinionValues } from "./schemas";

interface OpinionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entry: LibraryEntry;
  onSave: (values: OpinionValues) => Promise<void>;
}

/**
 * Your opinion of this thing — and only that.
 *
 * Shelf membership used to live here, which is what made putting a book on a shelf
 * mean opening a dialog named after something else. It is edited on the page now,
 * beside the shelves it lists. Format stayed: a format is a fact about your copy,
 * not an organizational tier, and it is not a shelf (DEC-059).
 */
export function OpinionDialog({
  open,
  onOpenChange,
  entry,
  onSave,
}: OpinionDialogProps) {
  const itemTypes = useItemTypes();
  const [saveError, setSaveError] = useState("");
  const form = useForm<OpinionValues>({
    resolver: zodResolver(opinionSchema),
    defaultValues: {
      status: entry.status,
      score: entry.score,
      notes: entry.notes ?? "",
      date_started: entry.date_started ?? "",
      date_finished: entry.date_finished ?? "",
      reread_count: String(entry.reread_count),
      // `String(null)` renders the word "null" in the box, and `String(undefined)`
      // renders "undefined" and makes the form permanently invalid — so the empty
      // case is spelled out, loosely, and covers a response that omits the field.
      progress: entry.progress == null ? "" : String(entry.progress),
      formats: entry.formats ?? [],
    },
  });
  const errors = form.formState.errors;
  // DEC-057: a record has no reread count and no started/finished dates, so this
  // asks the domain rather than branching on the type.
  const has = (field: EntryFieldName) =>
    hasEntryField(entry.item.type, itemTypes.data, field);
  // The domain's own word for the field. An anime has rewatches, not rereads.
  const nameOf = (field: EntryFieldName) =>
    entryFieldLabel(entry.item.type, itemTypes.data, field);
  const progress = progressFor(entry.item.type, itemTypes.data);
  const formats = formatsFor(entry.item.type, itemTypes.data);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit your opinion</DialogTitle>
          <DialogDescription>
            Your score, status, format and notes belong to you alone and are
            never overwritten by a provider.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={form.handleSubmit(async (values) => {
            setSaveError("");
            try {
              await onSave(values);
              onOpenChange(false);
            } catch (error) {
              // The dialog stays mounted so nothing typed is lost.
              setSaveError(
                error instanceof Error
                  ? error.message
                  : "Your change could not be saved",
              );
            }
          })}
        >
          <div>
            <span className="mb-1 block text-sm font-medium">Status</span>
            <Controller
              control={form.control}
              name="status"
              render={({ field }) => (
                <StatusSelect
                  statuses={statusesFor(entry.item.type, itemTypes.data)}
                  value={field.value}
                  onValueChange={field.onChange}
                  label="Status"
                />
              )}
            />
          </div>
          <Field id="opinion-score" label="Score" error={errors.score?.message}>
            {() => (
              <Controller
                control={form.control}
                name="score"
                render={({ field }) => (
                  <ScorePicker
                    value={field.value}
                    provisional={entry.score_provisional}
                    onChange={field.onChange}
                  />
                )}
              />
            )}
          </Field>
          <Field id="opinion-notes" label="Notes" error={errors.notes?.message}>
            {(props) => <Textarea {...props} {...form.register("notes")} />}
          </Field>
          {formats.length > 0 && (
            <div>
              <span className="mb-1 block text-sm font-medium">Format</span>
              {/* The same control as the add screen, and deliberately *not* the
                  shelf control: a format is a closed per-domain vocabulary you
                  pick from, a shelf is a tier you invent, and DEC-059 turns on
                  that distinction. Legal on any status, which is what makes
                  "wishlist → vinyl" expressible. */}
              <Controller
                control={form.control}
                name="formats"
                render={({ field }) => (
                  <FormatPicker
                    formats={formats}
                    value={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
            </div>
          )}
          {has("date_started") && (
            <Field
              id="opinion-started"
              label={nameOf("date_started")}
              error={errors.date_started?.message}
            >
              {(props) => (
                <Input
                  {...props}
                  type="date"
                  className="h-11"
                  {...form.register("date_started")}
                />
              )}
            </Field>
          )}
          {has("date_finished") && (
            <Field
              id="opinion-finished"
              label={nameOf("date_finished")}
              error={errors.date_finished?.message}
            >
              {(props) => (
                <Input
                  {...props}
                  type="date"
                  className="h-11"
                  {...form.register("date_finished")}
                />
              )}
            </Field>
          )}
          {has("reread_count") && (
            <Field
              id="opinion-rereads"
              label={nameOf("reread_count")}
              error={errors.reread_count?.message}
            >
              {(props) => (
                <Input
                  {...props}
                  type="number"
                  min="0"
                  className="h-11"
                  {...form.register("reread_count")}
                />
              )}
            </Field>
          )}
          {progress && (
            <Field
              id="opinion-progress"
              label={progress.label}
              error={errors.progress?.message}
            >
              {(props) => (
                <Input
                  {...props}
                  type="number"
                  min="0"
                  className="h-11"
                  {...form.register("progress")}
                />
              )}
            </Field>
          )}
          {saveError && (
            <p role="alert" className="text-sm text-destructive">
              {saveError}
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" className="rounded-full px-5">
              Save opinion
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
