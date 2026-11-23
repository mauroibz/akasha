import { Link } from "react-router-dom";

import { useItemTypes } from "@/features/library/useItemTypes";
import { useShownItemTypes } from "@/features/media/useMedia";
import { PlaySection } from "@/features/play/PlaySection";

const more = [
  { to: "/deck", label: "Tidy up", says: "covers, duplicates and the inbox" },
  {
    to: "/rank",
    label: "Rank",
    says: "put the things you scored alike in order",
  },
  { to: "/tiers", label: "Tiers", says: "your scores as rows" },
];

/**
 * Play, as the Journal's interactive part (Sprint 146, DEC-193): the games that
 * were at the top of Insights, asked of the medium the person keeps first, and the
 * ways into the decks that had no door but Settings and the command bar.
 */
export function PlayWidget() {
  const itemTypes = useItemTypes();
  const shown = useShownItemTypes();
  const type = shown.data?.[0]?.id ?? "";
  return (
    <div className="space-y-4">
      {type ? (
        <PlaySection type={type} types={itemTypes.data} headless />
      ) : null}
      <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
        {more.map((link) => (
          <li key={link.to}>
            <Link
              to={link.to}
              className="inline-flex min-h-11 items-center font-medium text-foreground underline decoration-primary decoration-2 underline-offset-4 focus-ring"
            >
              {link.label}
            </Link>
            <span className="ml-2">{link.says}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
