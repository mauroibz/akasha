import type { ImporterDefinition } from "@/api/imports";

/**
 * What a connector says about itself, rendered by a screen that never reads it.
 *
 * The steps arrive as plain strings from `ImportInputSpec.guide` and are rendered
 * as an ordered list — deliberately not markdown. A connector publishing markup
 * into a shared screen is a rendering dependency and an injection surface for one
 * benefit nobody asked for; ordered steps are what import guidance actually is
 * (DEC-080).
 */
export function ConnectorGuide({ importer }: { importer: ImporterDefinition }) {
  const { guide, help, help_url: helpUrl, kind, label } = importer.input;
  if (guide.length === 0 && !help && !helpUrl) return null;
  const headingId = `${importer.id}-guide-heading`;
  return (
    <section className="rounded-xl bg-surface-raised p-4">
      <h2 id={headingId} className="text-sm font-semibold text-foreground">
        {kind === "upload"
          ? `How to get a ${label}`
          : `Before you import from ${importer.label}`}
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
        // as leaving and opens beside the import rather than replacing it. The
        // wording follows the kind: Calibre has no export page, it has a manual.
        <a
          className="focus-ring mt-3 inline-block text-sm text-primary"
          href={helpUrl}
          target="_blank"
          rel="noreferrer noopener"
        >
          {kind === "upload"
            ? `Open the ${importer.label} export page`
            : `${importer.label} documentation`}{" "}
          ↗
        </a>
      )}
    </section>
  );
}
