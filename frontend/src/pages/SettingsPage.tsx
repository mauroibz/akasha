import { PageHeader } from "@/components/PageHeader";
import { Link } from "react-router-dom";

import { ExportPanel } from "@/features/export/ExportPanel";
import { SuggestionSources } from "@/features/suggest/SuggestionSources";
import { PageFrame } from "@/components/PageFrame";
import { YourMedia } from "@/features/media/YourMedia";
import { ThemePicker } from "@/features/theme/ThemePicker";

/**
 * Settings (Sprint 090): Appearance, then Suggestions (which sources this server has
 * on, Sprint 135), then Your data, the export that moved here from the import screen
 * in Sprint 096 (proposal §5.1).
 */
export function SettingsPage() {
  return (
    <PageFrame width="reading">
      <PageHeader title="Settings" />
      <h2 className="mt-8 font-display text-3xl font-medium tracking-tight">
        Appearance
      </h2>
      <ThemePicker className="mt-6" />
      <p className="mt-6 text-sm text-muted-foreground">
        Kept in this browser, so a phone and a laptop can differ. Covers, scores
        and the amber dot look the same in every theme.
      </p>
      <h2 className="mt-12 font-display text-3xl font-medium tracking-tight">
        Your media
      </h2>
      {/* The same control Arrange shows on the Library (Sprint 143). */}
      <YourMedia heading={false} className="mt-4" />
      <SuggestionSources />
      <ExportPanel embedded />
      {/* Upkeep (Sprint 112; *Tidy up* since Sprint 125): a data job, offered
          beside the export, as well as from the command bar. */}
      <p className="mt-6 text-sm text-muted-foreground">
        Covers, duplicates and the inbox, one card at a time.{" "}
        <Link
          to="/deck"
          className="inline-flex min-h-11 items-center font-medium text-primary-text underline-offset-4 hover:underline focus-ring"
        >
          Tidy up
        </Link>
      </p>
    </PageFrame>
  );
}
