import type { ImporterDefinition, ImportInputSpec } from "@/api/imports";

/**
 * Ordered steps and a help link, rendered from a declaration and nothing else.
 *
 * The steps arrive as plain strings and are rendered as an ordered list —
 * deliberately not markdown. A connector (or export view) publishing markup into a
 * shared screen is a rendering dependency and an injection surface for one benefit
 * nobody asked for; ordered steps are what both import and export guidance actually
 * are (DEC-080). `ConnectorGuide` below is the import side's own wording over this;
 * Sprint 069's export tab renders the same component directly with its own heading
 * and link label, so the declaration renderer is shared rather than copied.
 */
export function DeclarationGuide({
  headingId,
  heading,
  guide,
  help = null,
  helpUrl = null,
  helpLabel,
}: {
  headingId: string;
  heading: string;
  guide: readonly string[];
  help?: string | null;
  helpUrl?: string | null;
  helpLabel: string;
}) {
  if (guide.length === 0 && !help && !helpUrl) return null;
  return (
    <section className="rounded-xl bg-surface-raised p-4">
      <h2 id={headingId} className="text-sm font-semibold text-foreground">
        {heading}
      </h2>
      {guide.length > 0 && (
        <ol
          aria-labelledby={headingId}
          className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-muted-foreground"
        >
          {guide.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      )}
      {guide.length === 0 && help && (
        <p className="mt-2 text-sm text-muted-foreground">{help}</p>
      )}
      {helpUrl && (
        // The one place this application sends you off the LAN, so it is marked
        // as leaving and opens beside the flow rather than replacing it. The
        // wording follows the caller: Calibre has no export page, it has a manual.
        <a
          className="focus-ring mt-3 inline-block text-sm text-primary"
          href={helpUrl}
          target="_blank"
          rel="noreferrer noopener"
        >
          {helpLabel} ↗
        </a>
      )}
    </section>
  );
}

/**
 * What an importer says about itself, rendered by a screen that never reads it.
 *
 * `spec` defaults to the primary input but may be an alternate's own — an
 * alternate can have guidance the primary does not (DEC-081, generalized), and
 * this is what actually renders it rather than leaving it a declared-but-dead field.
 */
export function ConnectorGuide({
  importer,
  spec = importer.input,
  headingId: headingIdProp,
}: {
  importer: ImporterDefinition;
  spec?: ImportInputSpec;
  headingId?: string;
}) {
  const { guide, help, help_url: helpUrl, kind, label } = spec;
  const headingId = headingIdProp ?? `${importer.id}-guide-heading`;
  return (
    <DeclarationGuide
      headingId={headingId}
      heading={
        kind === "upload"
          ? `How to get a ${label}`
          : `Before you import from ${importer.label}`
      }
      guide={guide}
      help={help}
      helpUrl={helpUrl}
      helpLabel={
        kind === "upload"
          ? `Open the ${importer.label} export page`
          : `${importer.label} documentation`
      }
    />
  );
}
