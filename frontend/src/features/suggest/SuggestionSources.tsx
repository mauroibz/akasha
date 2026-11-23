import { useItemTypes } from "@/features/library/useItemTypes";

import { allSources } from "./recommendation";

/**
 * Settings' *Suggestions* (Sprint 135): each source that may suggest things, whether
 * this server has it configured, and for a hosted model which provider and model
 * answer and what is sent to it. Read from the item types the server already
 * publishes; nothing here can change the configuration, which is the server's
 * environment.
 */
export function SuggestionSources() {
  const types = useItemTypes();
  const sources = allSources(types.data);
  if (!sources.length) return null;
  return (
    <section aria-labelledby="suggestion-sources" className="mt-10">
      <h2
        id="suggestion-sources"
        className="font-display text-3xl font-medium tracking-tight"
      >
        Suggestions
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Where <em>More like this</em> asks. Set on the server, in its
        environment.
      </p>
      <ul className="mt-4 divide-y divide-border rounded-xl border border-border bg-surface">
        {sources.map((source) => (
          <li key={source.name} className="flex flex-col gap-1 p-3 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-medium">{source.label}</span>
              <span
                className={
                  source.configured
                    ? "text-xs font-medium text-foreground"
                    : "text-xs text-muted-foreground"
                }
              >
                {source.configured ? "On" : "Off"}
              </span>
            </div>
            {source.about?.model ? (
              <p className="text-muted-foreground">
                {source.about.provider_label ?? source.about.provider} ·{" "}
                <span className="font-mono text-xs">{source.about.model}</span>
              </p>
            ) : null}
            {source.about?.sends ? (
              <p className="text-muted-foreground">
                What it is sent: {source.about.sends}
              </p>
            ) : null}
            {!source.configured && source.hint ? (
              <p className="text-xs text-muted-foreground">{source.hint}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
