import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import {
  AUTH_STATE_QUERY_KEY,
  getAuthState,
  type AuthState,
  type AuthUser,
} from "@/api/auth";
import { AUTH_REQUIRED_EVENT } from "@/api/request";
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
const ShelfPage = lazy(async () => ({
  default: (await import("@/pages/ShelfPage")).ShelfPage,
}));
const InsightsPage = lazy(async () => ({
  default: (await import("@/pages/InsightsPage")).InsightsPage,
}));
const LoginPage = lazy(async () => ({
  default: (await import("@/pages/LoginPage")).LoginPage,
}));
const SetupPage = lazy(async () => ({
  default: (await import("@/pages/SetupPage")).SetupPage,
}));
const PeoplePage = lazy(async () => ({
  default: (await import("@/pages/PeoplePage")).PeoplePage,
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

function authenticatedState(user: AuthUser): AuthState {
  return {
    auth: "on",
    authenticated: true,
    setup_required: false,
    user,
  };
}

function currentDestination(pathname: string, search: string, hash: string) {
  return `${pathname}${search}${hash}`;
}

function AuthLoading() {
  return (
    <main
      className="flex min-h-screen items-center justify-center p-6"
      role="status"
      aria-live="polite"
    >
      <p className="text-sm text-muted-foreground">Opening Akasha…</p>
    </main>
  );
}

function PrivateRoutes({
  user,
  onSignedOut,
}: {
  user?: AuthUser | null;
  onSignedOut?: () => void;
}) {
  return (
    <AppShell user={user} onSignedOut={onSignedOut}>
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
            <Route path="/shelves/:slug" element={<ShelfPage />} />
            <Route path="/insights" element={<InsightsPage />} />
            <Route
              path="/people"
              element={
                user ? <PeoplePage user={user} /> : <Navigate to="/" replace />
              }
            />
            {/* Triage folded into Import as a tab (DEC-079). The old
                address stays live rather than 404ing: it was a top-level
                nav item for thirty sprints, so it is in bookmarks and in
                the history of anyone who used it. */}
            <Route
              path="/triage"
              element={<Navigate to="/import?tab=triage" replace />}
            />
            {/* A real address for the export tab, the same shape as
                /triage above (Sprint 069 deliverable 2). */}
            <Route
              path="/export"
              element={<Navigate to="/import?tab=export" replace />}
            />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/setup" element={<Navigate to="/" replace />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </RoutedErrorBoundary>
    </AppShell>
  );
}

/** Owns the authentication gate and the sole global refusal listener. */
export function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const client = useQueryClient();
  const authRedirecting = useRef(false);
  const [forcedLogin, setForcedLogin] = useState(false);
  const [resumeTo, setResumeTo] = useState<string | null>(null);
  const auth = useQuery({
    queryKey: AUTH_STATE_QUERY_KEY,
    queryFn: getAuthState,
    staleTime: Infinity,
    retry: false,
  });

  useEffect(() => {
    function requireAuthentication(event: Event) {
      if (authRedirecting.current) return;
      authRedirecting.current = true;
      const detail = (event as CustomEvent<{ kind?: "login" | "setup" }>)
        .detail;
      const destination = currentDestination(
        location.pathname,
        location.search,
        location.hash,
      );
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "auth",
      });
      client.getMutationCache().clear();
      setForcedLogin(detail?.kind !== "setup");
      void navigate(detail?.kind === "setup" ? "/setup" : "/login", {
        replace: true,
        state: {
          returnTo: destination,
          interrupted: detail?.kind !== "setup",
        },
      });
    }
    window.addEventListener(AUTH_REQUIRED_EVENT, requireAuthentication);
    return () =>
      window.removeEventListener(AUTH_REQUIRED_EVENT, requireAuthentication);
  }, [client, location.hash, location.pathname, location.search, navigate]);

  useEffect(() => {
    if (
      resumeTo ===
      currentDestination(location.pathname, location.search, location.hash)
    ) {
      setResumeTo(null);
    }
  }, [location.hash, location.pathname, location.search, resumeTo]);

  if (auth.isPending) return <AuthLoading />;
  if (auth.isError) {
    return (
      <RouteErrorPage
        error={{ message: "Akasha could not check your session." }}
        reset={() => void auth.refetch()}
      />
    );
  }

  const state = auth.data;
  if (state.auth === "off") {
    return <PrivateRoutes />;
  }

  if (resumeTo) return <Navigate to={resumeTo} replace />;

  const returnTo = currentDestination(
    location.pathname,
    location.search,
    location.hash,
  );
  if (state.setup_required) {
    if (location.pathname !== "/setup") {
      return <Navigate to="/setup" replace state={{ returnTo }} />;
    }
    return (
      <Suspense fallback={<AuthLoading />}>
        <SetupPage
          onAuthenticated={(user) => {
            client.setQueryData(AUTH_STATE_QUERY_KEY, authenticatedState(user));
            authRedirecting.current = false;
          }}
          onNavigate={setResumeTo}
        />
      </Suspense>
    );
  }
  if (!state.authenticated || forcedLogin) {
    if (location.pathname !== "/login") {
      return (
        <Navigate
          to="/login"
          replace
          state={{ returnTo, interrupted: forcedLogin }}
        />
      );
    }
    return (
      <Suspense fallback={<AuthLoading />}>
        <LoginPage
          onAuthenticated={(user) => {
            client.setQueryData(AUTH_STATE_QUERY_KEY, authenticatedState(user));
            authRedirecting.current = false;
            setForcedLogin(false);
          }}
          onNavigate={setResumeTo}
        />
      </Suspense>
    );
  }
  return (
    <PrivateRoutes
      user={state.user}
      onSignedOut={() => {
        client.removeQueries({
          predicate: (query) => query.queryKey[0] !== "auth",
        });
        client.getMutationCache().clear();
        client.setQueryData<AuthState>(AUTH_STATE_QUERY_KEY, {
          auth: "on",
          authenticated: false,
          setup_required: false,
          user: null,
        });
      }}
    />
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
