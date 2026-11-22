import { QueryClient } from "@tanstack/react-query";

/**
 * The application's query cache (Sprint 129).
 *
 * React Query's defaults treat every result as stale at once and refetch it on
 * every window focus. For the library that meant each loaded page of the list was
 * fetched again, one after another, every time the reader switched back to the
 * tab. Data here changes when this tab writes it, and every write invalidates the
 * queries it touches; background work announces itself on `/api/events`. So:
 *
 * - a result stays fresh for 30 seconds, and leaving a screen and coming back
 *   inside that window does not ask the server again;
 * - focusing the window refetches nothing by default. A query that must notice
 *   another device's change (the Inbox count) opts back in on its own.
 *
 * Invalidation is unaffected: it marks a query stale whatever its age, so a write
 * still refreshes what it changed.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
    },
  });
}
