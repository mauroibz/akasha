import { useCallback, useEffect, useRef, useState } from "react";

import { searchCandidates, type SearchCandidate } from "@/api/add";

export interface WebSearchState {
  /** The query the results belong to, or "" when nothing has been searched. */
  query: string;
  results: SearchCandidate[];
  pending: boolean;
  error: string;
  warning: string;
}

const idle: WebSearchState = {
  query: "",
  results: [],
  pending: false,
  error: "",
  warning: "",
};

/**
 * Provider search, as the library page spends it.
 *
 * The quota is the thing to get wrong here. A provider search costs one request per
 * provider at a five-second timeout, counted against a daily budget of 900 against a
 * real ceiling of 1,000 (DEC-045), and DEC-044 already measured one tier breach. So
 * this hook is built around not spending: it remembers every string it has searched
 * and refuses to search it twice, and it serves a repeat from what it already has.
 *
 * Two guards that look like tidiness and are not:
 *
 * - **The abort** stops a superseded request rather than leaving it to run. Without
 *   it a few keystrokes leave several multi-second requests open against a
 *   rate-limited free API for results nobody will read.
 * - **The request id** decides which response is allowed to land, so a slow earlier
 *   search cannot overwrite a faster later one.
 *
 * What it deliberately does not decide is *when* to search. That rule — settled, at
 * least three characters, and nothing in the library — belongs to the page, because
 * only the page knows whether the library answered.
 */
export function useWebSearch(itemType: string) {
  const [state, setState] = useState<WebSearchState>(idle);
  const requestId = useRef(0);
  const inFlight = useRef<AbortController | null>(null);
  const searched = useRef(new Set<string>());
  const cache = useRef(new Map<string, SearchCandidate[]>());

  const keyFor = useCallback(
    (raw: string) => `${itemType}:${raw.trim()}`,
    [itemType],
  );

  const search = useCallback(
    (raw: string) => {
      const query = raw.trim();
      if (!query) return;
      const key = keyFor(query);
      const cached = cache.current.get(key);
      if (cached) {
        setState({ ...idle, query, results: cached });
        return;
      }
      searched.current.add(key);
      const id = ++requestId.current;
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;
      setState({ ...idle, query, pending: true });
      void searchCandidates(query, itemType, controller.signal)
        .then((value) => {
          if (requestId.current !== id) return;
          cache.current.set(key, value.items);
          setState({
            ...idle,
            query,
            results: value.items,
            warning: value.warning ?? "",
          });
        })
        .catch((e: Error) => {
          // An abort is this hook's own cleanup, not a failure to report.
          if (e.name === "AbortError") return;
          if (requestId.current !== id) return;
          setState({ ...idle, query, error: e.message });
        });
    },
    [itemType, keyFor],
  );

  /** Whether this exact string has already cost a request for this domain. */
  const hasSearched = useCallback(
    (raw: string) => searched.current.has(keyFor(raw)),
    [keyFor],
  );

  const clear = useCallback(() => {
    requestId.current += 1;
    inFlight.current?.abort();
    setState(idle);
  }, []);

  // Results belong to the domain that produced them. Switching domain does not
  // spend anything, but it must not leave records on screen under Books.
  useEffect(() => {
    setState(idle);
  }, [itemType]);

  useEffect(() => () => inFlight.current?.abort(), []);

  return { ...state, search, hasSearched, clear };
}
