import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import type { LibraryItem } from "@/api/library";
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
  onSave: (values: MetadataValues) => Promise<void>;
}

function asText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

export function MetadataDialog({
  open,
  onOpenChange,
  item,
  onSave,
}: MetadataDialogProps) {
  const [saveError, setSaveError] = useState("");
  const form = useForm<MetadataValues>({
    resolver: zodResolver(metadataSchema),
    defaultValues: {
      title: item.title,
      subtitle: item.subtitle ?? "",
      year: asText(item.year),
      authors: Array.isArray(item.metadata.authors)
        ? item.metadata.authors.join(", ")
        : "",
      // Left empty rather than prefilled with `creator_sort`: an untouched field
      // must keep following the authors above, and the automatic value is shown
      // as the placeholder instead.
      creator_sort_override: item.creator_sort_override ?? "",
      publisher: asText(item.metadata.publisher),
      language: asText(item.metadata.language),
      page_count: asText(item.metadata.page_count),
      description: asText(item.metadata.description),
      subjects: (item.metadata.subjects ?? []).join(", "),
      series: asText(item.metadata.series),
      original_year: asText(item.metadata.original_year),
    },
  });
  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit shared book metadata</DialogTitle>
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
                  : "Book metadata could not be saved",
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
            id="metadata-authors"
            label="Authors"
            error={errors.authors?.message}
          >
            {(props) => (
              <Input
                {...props}
                className="h-11"
                {...form.register("authors")}
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
                  Where this sits in an author-sorted list. Leave it empty to
                  follow the authors above.
                </p>
              </>
            )}
          </Field>
          <Field
            id="metadata-publisher"
            label="Publisher"
            error={errors.publisher?.message}
          >
            {(props) => (
              <Input
                {...props}
                className="h-11"
                {...form.register("publisher")}
              />
            )}
          </Field>
          <Field
            id="metadata-language"
            label="Language"
            error={errors.language?.message}
          >
            {(props) => (
              <Input
                {...props}
                className="h-11"
                {...form.register("language")}
              />
            )}
          </Field>
          <Field
            id="metadata-pages"
            label="Page count"
            error={errors.page_count?.message}
          >
            {(props) => (
              <Input
                {...props}
                type="number"
                min="1"
                className="h-11"
                {...form.register("page_count")}
              />
            )}
          </Field>
          <Field
            id="metadata-description"
            label="Description"
            error={errors.description?.message}
          >
            {(props) => (
              <Textarea {...props} {...form.register("description")} />
            )}
          </Field>
          <Field
            id="metadata-subjects"
            label="Subjects, comma separated"
            error={errors.subjects?.message}
          >
            {(props) => (
              <Input
                {...props}
                className="h-11"
                {...form.register("subjects")}
              />
            )}
          </Field>
          <Field
            id="metadata-series"
            label="Series"
            error={errors.series?.message}
          >
            {(props) => (
              <Input {...props} className="h-11" {...form.register("series")} />
            )}
          </Field>
          <Field
            id="metadata-original-year"
            label="Original publication year"
            error={errors.original_year?.message}
          >
            {(props) => (
              <Input
                {...props}
                type="number"
                className="h-11"
                {...form.register("original_year")}
              />
            )}
          </Field>
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
