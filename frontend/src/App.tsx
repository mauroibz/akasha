import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppShell } from "@/components/AppShell";
import { HomePage } from "@/pages/HomePage";
import { AddPage } from "@/pages/AddPage";
import { DetailPage } from "@/pages/DetailPage";
import { ImportPage } from "@/pages/ImportPage";
import { ShelvesPage } from "@/pages/ShelvesPage";
import { TriagePage } from "@/pages/TriagePage";
import { NotFoundPage, RouteErrorPage } from "@/pages/NotFoundPage";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell>
          <ErrorBoundary
            fallback={(error, reset) => (
              <RouteErrorPage error={error} reset={reset} />
            )}
          >
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/add" element={<AddPage />} />
              <Route path="/books/:entryId" element={<DetailPage />} />
              <Route path="/import" element={<ImportPage />} />
              <Route path="/shelves" element={<ShelvesPage />} />
              <Route path="/triage" element={<TriagePage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </ErrorBoundary>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
