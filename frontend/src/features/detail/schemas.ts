import { z } from "zod";

import { entryFormats, entryStatuses, type FieldSpec } from "@/api/library";

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
    // The union; which of them this entry may hold is its domain's business and is
    // enforced on the server against the item's own type (DEC-059).
    formats: z.array(z.enum(entryFormats)),
  })
  .refine(
    (value) =>
      !value.date_started ||
      !value.date_finished ||
      value.date_finished >= value.date_started,
    { message: "Finished cannot be before started", path: ["date_finished"] },
  );

export type OpinionValues = z.infer<typeof opinionSchema>;

export type MetadataValues = Record<string, string>;

/**
 * The metadata form is built from the field spec the API publishes, not from a list
 * of book fields typed into this file (DEC-052 seam 3). The four item columns beside
 * it — title, subtitle, year, and the sort-name override — belong to every domain and
 * stay here.
 */
export function metadataSchema(
  fields: FieldSpec[],
): z.ZodType<MetadataValues, MetadataValues> {
  const shape: Record<string, z.ZodType<string>> = {
    title: z.string().trim().min(1, "A title is required"),
    subtitle: z.string(),
    year: optionalNumber("Use a year between 0 and 9999", 0, 9999),
    creator_sort_override: z.string().max(300, "That is too long to be a name"),
  };
  for (const field of fields) {
    shape[field.name] =
      field.type === "number"
        ? optionalNumber(
            numberMessage(field),
            field.minimum ?? 0,
            field.maximum ?? 9999,
          )
        : z.string();
  }
  // Zod infers `unknown` for a shape built at runtime; every branch above
  // produces a string, which is what the form reads and writes.
  return z.object(shape) as unknown as z.ZodType<
    MetadataValues,
    MetadataValues
  >;
}

function numberMessage(field: FieldSpec): string {
  if (
    field.minimum !== null &&
    field.minimum !== undefined &&
    field.minimum > 0
  )
    return `${field.label} must be ${field.minimum} or more`;
  return `${field.label} must be a whole number`;
}

/** The metadata half of the patch: only the fields this domain declares. */
export function toMetadataPatch(
  values: MetadataValues,
  fields: FieldSpec[],
): Record<string, unknown> {
  const patch: Record<string, unknown> = {};
  for (const field of fields) {
    const raw = values[field.name] ?? "";
    if (field.multiplicity === "many") patch[field.name] = splitList(raw);
    else if (field.type === "number") patch[field.name] = optionalInt(raw);
    else patch[field.name] = raw || null;
  }
  return patch;
}

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
