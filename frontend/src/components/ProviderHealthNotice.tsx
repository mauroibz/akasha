import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";

import { getProviderHealth } from "@/api/health";

/**
 * Says which metadata provider is unavailable and why, rather than letting a
 * search quietly return half its results. Fed by `GET /api/health/providers`,
 * which Sprint 014 added; this invents no endpoint of its own.
 *
 * Provider health is a property of the deployment, not of the query, so it is
 * cached for a minute instead of refetched per keystroke. A failure to read it
 * renders nothing: the notice must never be the reason a search page breaks.
 */
export function ProviderHealthNotice() {
  const health = useQuery({
    queryKey: ["provider-health"],
    queryFn: getProviderHealth,
    staleTime: 60_000,
    retry: false,
  });

  if (!health.data?.degraded) return null;
  const unavailable = health.data.providers.filter(
    (provider) => !provider.available,
  );
  if (unavailable.length === 0) return null;

  return (
    <div
      role="status"
      className="mt-4 flex items-start gap-3 rounded-xl border border-primary/40 bg-primary/10 p-4 text-sm"
    >
      <TriangleAlert
        aria-hidden="true"
        className="mt-0.5 h-4 w-4 shrink-0 text-primary"
      />
      <div>
        <p className="font-medium">Search is running on fewer providers</p>
        <ul className="mt-1 space-y-0.5 text-muted-foreground">
          {unavailable.map((provider) => (
            <li key={provider.name}>
              {provider.name} is unavailable
              {provider.reason ? `: ${provider.reason}` : ""}
            </li>
          ))}
        </ul>
        <p className="mt-1 text-muted-foreground">
          Results may be missing editions. You can still enter it by hand.
        </p>
      </div>
    </div>
  );
}
