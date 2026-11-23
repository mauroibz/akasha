import { Link } from "react-router-dom";

import type { HomeLent, ModuleSize } from "@/api/home";

import { HomeModule } from "./HomeModule";
import { localDate } from "./year";

const SHOWN: Record<ModuleSize, number> = { S: 3, M: 4, L: 5 };

const SINCE = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

/**
 * What is out (Sprint 131): open loans, longest out first, who has each and since
 * when. Hidden when nothing is lent.
 */
export function LentOut({
  lent,
  size,
  className,
}: {
  lent: HomeLent;
  size: ModuleSize;
  className?: string;
}) {
  return (
    <HomeModule
      title="Lent out"
      className={className}
      aside={
        <Link
          to="/lent"
          className="underline-offset-4 hover:text-foreground hover:underline focus-ring"
        >
          {lent.total} out →
        </Link>
      }
    >
      <ul className="space-y-1.5">
        {lent.loans.slice(0, SHOWN[size]).map((loan) => (
          <li key={loan.id} className="min-w-0 text-sm">
            <Link
              to={`/books/${loan.entry.id}`}
              className="block truncate font-medium underline-offset-4 hover:underline focus-ring"
            >
              {loan.entry.item.title}
            </Link>
            <span className="block truncate text-xs text-muted-foreground">
              {loan.person} · since{" "}
              {SINCE.format(localDate(loan.lent_on.slice(0, 10)))}
            </span>
          </li>
        ))}
      </ul>
    </HomeModule>
  );
}
