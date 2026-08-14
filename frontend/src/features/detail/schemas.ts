import { z } from "zod";

import { entryStatuses } from "@/api/library";

/**
 * Validation for the two detail forms. Technical spec section 8 requires schema
 * validation on every form and that a failed write never silently loses input,
 * so these run before the request and the dialogs stay mounted on failure.
 */

/** An empty string means "not set"; anything else must be a real calendar day. */
const optionalIsoDate = z
  .string()
  .trim()
  .refine(
    (value) =>
      value === "" ||
      (/^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value))),
    { message: "Use a date like 2026-08-11" },
  );

/** Number inputs hand back strings, including "" when cleared. */
function optionalNumber(message: string, min: number, max: number) {
  return z
    .string()
    .trim()
    .refine(
      (value) => {
        if (value === "") return true;
        const parsed = Number(value);
        return Number.isInteger(parsed) && parsed >= min && parsed <= max;
      },
      { message },
    );
}

export const opinionSchema = z
  .object({
    status: z.enum(entryStatuses),
    score: z
      .number()
      .int()
      .min(1, "A score runs from 1 to 10")
      .max(10, "A score runs from 1 to 10")
      .nullable(),
    notes: z.string(),
    date_started: optionalIsoDate,
    date_finished: optionalIsoDate,
    reread_count: optionalNumber("Rereads must be between 0 and 9999", 0, 9999),
    shelf_ids: z.array(z.number()),
  })
  .refine(
    (value) =>
      !value.date_started ||
      !value.date_finished ||
      value.date_finished >= value.date_started,
    { message: "Finished cannot be before started", path: ["date_finished"] },
  );

export type OpinionValues = z.infer<typeof opinionSchema>;

export const metadataSchema = z.object({
  title: z.string().trim().min(1, "A book needs a title"),
  subtitle: z.string(),
  year: optionalNumber("Use a year between 0 and 9999", 0, 9999),
  authors: z.string(),
  creator_sort_override: z.string().max(300, "That is too long to be a name"),
  publisher: z.string(),
  language: z.string(),
  page_count: optionalNumber("Page count must be 1 or more", 1, 100_000),
  description: z.string(),
  subjects: z.string(),
  series: z.string(),
  original_year: optionalNumber("Use a year between 0 and 9999", 0, 9999),
});

export type MetadataValues = z.infer<typeof metadataSchema>;

/** "Borges, Bioy Casares" -> ["Borges", "Bioy Casares"] */
export function splitList(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function optionalInt(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

/** The manual-entry form on /add: the same rules as the metadata dialog. */
export const manualBookSchema = z.object({
  title: z.string().trim().min(1, "A book needs a title"),
  authors: z.string(),
  subtitle: z.string(),
  year: optionalNumber("Use a year between 0 and 9999", 0, 9999),
  isbn: z
    .string()
    .trim()
    .refine((value) => value === "" || /^[0-9Xx-]{10,17}$/.test(value), {
      message: "An ISBN is 10 or 13 digits",
    }),
});

export type ManualBookValues = z.infer<typeof manualBookSchema>;
