import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import type { FieldSpec, LibraryItem } from "@/api/library";
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
import { metadataSchema, type MetadataValues } from "./schemas";

interface MetadataDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: LibraryItem;
  /** What this item's domain says its metadata fields are (DEC-052 seam 3). */
  fields: FieldSpec[];
  onSave: (values: MetadataValues) => Promise<void>;
}

function asText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

/** A stored value as the form edits it: a list becomes a comma-separated line. */
function asFormValue(value: unknown, field: FieldSpec): string {
  if (field.multiplicity === "many")
    return Array.isArray(value) ? value.join(", ") : "";
  return asText(value);
}

export function MetadataDialog({
  open,
  onOpenChange,
  item,
  fields,
  onSave,
}: MetadataDialogProps) {
  const [saveError, setSaveError] = useState("");
  const form = useForm<MetadataValues>({
    resolver: zodResolver(metadataSchema(fields)),
    defaultValues: {
      title: item.title,
      subtitle: item.subtitle ?? "",
      year: asText(item.year),
      // Left empty rather than prefilled with `creator_sort`: an untouched field
      // must keep following the creators above, and the automatic value is shown
      // as the placeholder instead.
      creator_sort_override: item.creator_sort_override ?? "",
      ...Object.fromEntries(
        fields.map((field) => [
          field.name,
          asFormValue(item.metadata[field.name], field),
        ]),
      ),
    },
  });
  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit shared metadata</DialogTitle>
          <DialogDescription>
            These facts describe the edition and are shared by everyone who owns
            it. Your score, status, dates, notes, and shelves are separate.
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
                  : "Metadata could not be saved",
              );
            }
          })}
        >
          <Field
            id="metadata-title"
            label="Title"
            error={errors.title?.message}
          >
            {(props) => (
              <Input
                {...props}
                autoFocus
                className="h-11"
                {...form.register("title")}
              />
            )}
          </Field>
          <Field
            id="metadata-subtitle"
            label="Subtitle"
            error={errors.subtitle?.message}
          >
            {(props) => (
              <Input
                {...props}
                className="h-11"
                {...form.register("subtitle")}
              />
            )}
          </Field>
          <Field id="metadata-year" label="Year" error={errors.year?.message}>
            {(props) => (
              <Input
                {...props}
                type="number"
                className="h-11"
                {...form.register("year")}
              />
            )}
          </Field>
          <Field
            id="metadata-creator-sort"
            label="Sorts as"
            error={errors.creator_sort_override?.message}
          >
            {(props) => (
              <>
                <Input
                  {...props}
                  aria-describedby={
                    props["aria-describedby"] ?? "metadata-creator-sort-hint"
                  }
                  className="h-11"
                  placeholder={item.creator_sort ?? ""}
                  {...form.register("creator_sort_override")}
                />
                <p
                  id="metadata-creator-sort-hint"
                  className="mt-1 text-xs text-muted-foreground"
                >
                  Where this sits in a creator-sorted list. Leave it empty to
                  follow the creators above.
                </p>
              </>
            )}
          </Field>
          {fields.map((field) => (
            <Field
              key={field.name}
              id={`metadata-${field.name}`}
              label={
                field.multiplicity === "many"
                  ? `${field.label}, comma separated`
                  : field.label
              }
              error={errors[field.name]?.message}
            >
              {(props) =>
                field.type === "long_text" ? (
                  <Textarea {...props} {...form.register(field.name)} />
                ) : (
                  <Input
                    {...props}
                    className="h-11"
                    {...(field.type === "number"
                      ? {
                          type: "number",
                          min: field.minimum ?? undefined,
                          max: field.maximum ?? undefined,
                        }
                      : {})}
                    {...form.register(field.name)}
                  />
                )
              }
            </Field>
          ))}
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
              Save metadata
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
