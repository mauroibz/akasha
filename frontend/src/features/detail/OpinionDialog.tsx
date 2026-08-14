import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import type { LibraryEntry } from "@/api/library";
import type { ShelfWithCount } from "@/api/shelves";
import { ScorePicker } from "@/components/ScorePicker";
import { StatusSelect } from "@/components/StatusSelect";
import { statusLabelsFor } from "@/features/library/labels";
import { useItemTypes } from "@/features/library/useItemTypes";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "./Field";
import { opinionSchema, type OpinionValues } from "./schemas";

interface OpinionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entry: LibraryEntry;
  shelves: ShelfWithCount[];
  onSave: (values: OpinionValues) => Promise<void>;
  onCreateShelf: (name: string) => Promise<void>;
}

export function OpinionDialog({
  open,
  onOpenChange,
  entry,
  shelves,
  onSave,
  onCreateShelf,
}: OpinionDialogProps) {
  const itemTypes = useItemTypes();
  const [newShelfName, setNewShelfName] = useState("");
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
      shelf_ids: entry.shelves.map((shelf) => shelf.id),
    },
  });
  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit your opinion</DialogTitle>
          <DialogDescription>
            Your score, status, dates, notes, and shelves belong to you alone
            and are never overwritten by a provider.
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
                  labels={statusLabelsFor(entry.item.type, itemTypes.data)}
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
          <Field
            id="opinion-started"
            label="Started"
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
          <Field
            id="opinion-finished"
            label="Finished"
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
          <Field
            id="opinion-rereads"
            label="Reread count"
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
          {shelves.length > 0 && (
            <fieldset>
              <legend className="text-sm font-medium">Shelves</legend>
              <Controller
                control={form.control}
                name="shelf_ids"
                render={({ field }) => (
                  <div className="mt-2 flex flex-wrap gap-3">
                    {shelves.map((shelf) => (
                      <div key={shelf.id} className="flex items-center gap-2">
                        <Checkbox
                          id={`opinion-shelf-${shelf.id}`}
                          checked={field.value.includes(shelf.id)}
                          onCheckedChange={(checked) =>
                            field.onChange(
                              checked
                                ? [...field.value, shelf.id]
                                : field.value.filter(
                                    (id: number) => id !== shelf.id,
                                  ),
                            )
                          }
                        />
                        <Label htmlFor={`opinion-shelf-${shelf.id}`}>
                          {shelf.name}
                        </Label>
                      </div>
                    ))}
                  </div>
                )}
              />
            </fieldset>
          )}
          <div className="flex gap-2">
            <Input
              className="h-11 flex-1"
              aria-label="New shelf name"
              placeholder="New shelf name"
              value={newShelfName}
              onChange={(event) => setNewShelfName(event.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              className="rounded-full"
              disabled={!newShelfName.trim()}
              onClick={async () => {
                await onCreateShelf(newShelfName.trim());
                setNewShelfName("");
              }}
            >
              Create shelf
            </Button>
          </div>
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
