import type {
  ItemType,
  LibraryEntry,
  OutlinePart,
  ProgressSpec,
} from "@/api/library";
import { ApiError } from "@/api/request";

/** What the tracker needs to know about one entry, read from declarations alone. */
export interface OutlineContext {
  progress: ProgressSpec;
  /** The parts to draw, or empty when nothing says how many. */
  outline: OutlinePart[];
  /** What one part is called: the parts field's first column ("Season"). */
  partLabel: string | null;
  /** The domain lists parts (seasons) and this item has none yet: offer to load them. */
  partsMissing: boolean;
  /** There is no outline and the domain's total is a number the owner can type. */
  totalField: string | null;
}

export function outlineContext(
  entry: LibraryEntry,
  types: ItemType[] | undefined,
): OutlineContext | null {
  const domain = types?.find((type) => type.id === entry.item.type);
  const progress = domain?.progress;
  if (!domain || !progress) return null;
  const partsField = progress.parts_field ?? null;
  const parts = partsField
    ? domain.fields.find((field) => field.name === partsField)
    : undefined;
  const stored = partsField ? entry.item.metadata[partsField] : undefined;
  const outline = entry.item.outline ?? [];
  return {
    progress,
    outline,
    partLabel: parts?.columns?.[0]?.label ?? null,
    partsMissing:
      Boolean(partsField) && !(Array.isArray(stored) && stored.length > 0),
    totalField: outline.length === 0 ? progress.total_field : null,
  };
}

/** The abandoned status of an entry's domain, when the entry is in it (DEC-172). */
export function isAbandoned(
  itemType: string,
  status: string,
  types: ItemType[] | undefined,
): boolean {
  return Boolean(
    types
      ?.find((type) => type.id === itemType)
      ?.statuses.find((row) => row.value === status)?.abandoned,
  );
}

/** What to say when the outline action finds nothing, or cannot ask. */
export function outlineFailure(error: Error, unit: string): string {
  if (error instanceof ApiError && error.code === "outline_unavailable")
    return `No ${unit} list was found for this one.`;
  return `The ${unit} list could not be reached. Try again later.`;
}
