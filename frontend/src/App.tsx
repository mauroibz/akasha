import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { RoutedErrorBoundary } from "@/components/ErrorBoundary";
import { AppShell } from "@/components/AppShell";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage, RouteErrorPage } from "@/pages/NotFoundPage";

// `/` is the screen the application opens on, so it stays in the entry chunk.
// Everything else is reached by a deliberate navigation and can arrive then:
// Sprint 016 left a single 696 kB bundle that every cold load parsed in full,
// against a 500 ms first-page budget on a ZimaBoard (DEC-037).
const AddPage = lazy(async () => ({
  default: (await import("@/pages/AddPage")).AddPage,
}));
const DetailPage = lazy(async () => ({
  default: (await import("@/pages/DetailPage")).DetailPage,
}));
const ImportPage = lazy(async () => ({
  default: (await import("@/pages/ImportPage")).ImportPage,
}));
const ShelvesPage = lazy(async () => ({
  default: (await import("@/pages/ShelvesPage")).ShelvesPage,
}));
const InsightsPage = lazy(async () => ({
  default: (await import("@/pages/InsightsPage")).InsightsPage,
}));

/**
 * Occupies the main region while a route chunk arrives.
 *
 * `role="status"` rather than a bare spinner: a screen reader user gets told the
 * page is loading instead of meeting silence, and it is one live region, not a
 * second one beside a visible surface (DEC-028).
 */
function RouteFallback() {
  return (
    <main className="p-6" role="status" aria-live="polite">
      <p className="text-sm text-muted-foreground">Loading…</p>
    </main>
  );
}

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell>
          <RoutedErrorBoundary
            fallback={(error, reset) => (
              <RouteErrorPage error={error} reset={reset} />
            )}
          >
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/add" element={<AddPage />} />
                <Route path="/books/:entryId" element={<DetailPage />} />
                <Route path="/import" element={<ImportPage />} />
                <Route path="/shelves" element={<ShelvesPage />} />
                <Route path="/insights" element={<InsightsPage />} />
                {/* Triage folded into Import as a tab (DEC-079). The old
                    address stays live rather than 404ing: it was a top-level
                    nav item for thirty sprints, so it is in bookmarks and in
                    the history of anyone who used it. */}
                <Route
                  path="/triage"
                  element={<Navigate to="/import?tab=triage" replace />}
                />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </RoutedErrorBoundary>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
