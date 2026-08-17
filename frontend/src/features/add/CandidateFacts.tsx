import type { SearchCandidate } from "@/api/add";
import type { FieldSpec } from "@/api/library";

/**
 * What we already know about the thing you just clicked.
 *
 * The owner's report was that this screen "feels empty". It was: a search response
 * carries title, subtitle, creators, credit, year, original year, language and every
 * identifier the provider had, and the confirm screen rendered three of those and
 * discarded the rest. Nothing here costs a request — the data is already in the
 * browser by the time a result can be clicked.
 *
 * The domain half is rendered from the field spec `GET /api/item-types` publishes,
 * so a record shows its label and a book its publisher without this component
 * knowing that either exists (DEC-052 seam 3).
 */
export function CandidateFacts({
  candidate,
  fields,
}: {
  candidate: SearchCandidate;
  fields: FieldSpec[];
}) {
  // Both domains declare `language`, and books declare `original_year`, so a naive
  // identity block renders "Language: eng" twice — once from the candidate's own
  // column and once from the field spec. The domain's label wins where the two
  // overlap, and the candidate's column is the fallback value for it.
  const declared = new Set(fields.map((field) => field.name));
  const fallbacks: Record<string, unknown> = {
    language: candidate.language,
    original_year: candidate.original_year,
  };

  const identity: Array<[string, string]> = [];
  if (candidate.subtitle) identity.push(["Subtitle", candidate.subtitle]);
  if (candidate.year != null) identity.push(["Year", String(candidate.year)]);
  if (
    !declared.has("original_year") &&
    candidate.original_year != null &&
    // Only when it says something the edition year does not.
    candidate.original_year !== candidate.year
  )
    identity.push(["Originally published", String(candidate.original_year)]);
  if (!declared.has("language") && candidate.language)
    identity.push(["Language", candidate.language]);

  const domainFacts = fields
    .filter((field) => field.name !== "creators" && field.type !== "rows")
    .map(
      (field) =>
        [
          field,
          candidate.metadata[field.name] ?? fallbacks[field.name],
        ] as const,
    )
    .filter(
      ([, value]) => value !== null && value !== undefined && value !== "",
    )
    .map(([field, value]) => {
      const text = Array.isArray(value) ? value.join(", ") : String(value);
      return [field, text] as const;
    })
    .filter(([, text]) => text.length > 0);

  // A paragraph is not a fact, and a paragraph in one column of two is a ribbon:
  // twenty characters wide and the height of the panel. The detail page already
  // splits its fields this way (`inlineFields` / `blockFields`), so this is the
  // same rule in the other place a domain's fields are rendered. It reads the
  // declared type rather than the field's name, so a domain that adds its own
  // long field gets it without this component learning the name.
  const inlineFacts = domainFacts.filter(
    ([field]) => field.type !== "long_text",
  );
  const blockFacts = domainFacts.filter(
    ([field]) => field.type === "long_text",
  );

  const identifiers = Object.entries(candidate.identifiers ?? {});
  const rows: Array<[string, string]> = [
    ...identity,
    ...inlineFacts.map(
      ([field, text]) => [field.label, text] as [string, string],
    ),
  ];
  if (!rows.length && !blockFacts.length && !identifiers.length) return null;

  return (
    <section
      aria-label="What we know"
      className="rounded-xl border border-border p-4"
      data-candidate-facts=""
    >
      <h3 className="text-xs font-semibold uppercase tracking-wider text-primary">
        What we know
      </h3>
      <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="whitespace-pre-wrap break-words text-sm">{value}</dd>
          </div>
        ))}
        {blockFacts.map(([field, text]) => (
          <div
            key={field.name}
            className="min-w-0 sm:col-span-2"
            data-block-fact=""
          >
            <dt className="text-xs text-muted-foreground">{field.label}</dt>
            {/* Wraps rather than truncates: a description is the reason somebody
                pressed the button that fetched it. */}
            <dd className="whitespace-pre-wrap break-words text-sm">{text}</dd>
          </div>
        ))}
        {identifiers.length > 0 && (
          <div className="min-w-0 sm:col-span-2">
            <dt className="text-xs text-muted-foreground">Identifiers</dt>
            <dd className="break-words text-sm">
              {identifiers
                .map(([key, value]) => `${key}: ${value}`)
                .join(" · ")}
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}
