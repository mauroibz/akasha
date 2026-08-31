import { vi } from "vitest";

/**
 * The fetch mock every component test shares.
 *
 * The suite's noise floor used to be set here: a DetailPage test whose
 * hand-rolled mock had no branch for the attachments query answered it with
 * the *entry* JSON, so `body.attachments` was `undefined` and React Query
 * printed `Query data cannot be undefined` — twenty-one times on a green run,
 * burying any real warning.
 *
 * The rule this helper keeps: **every endpoint the app queries answers a
 * defined value**, in three layers:
 *
 * 1. the test's `router` — only the endpoints the test cares about;
 * 2. the specific defaults — `/api/shelves` → `[]`, `/api/item-types` → `[]`,
 *    `…/attachments` → `{ attachments: [] }` — so a query the test forgot
 *    still gets a *defined* value of the right shape;
 * 3. the `fallback` — the payload a bare GET answers (usually the entry
 *    fixture), for the endpoint the page is actually about.
 *
 * What it deliberately does not do: answer an endpoint nobody named. With no
 * `fallback`, an unknown URL rejects, so a test that watches a new endpoint
 * appear fails loudly rather than silently passing against a stub.
 */

export type ApiHandler = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Response | undefined | Promise<Response | undefined>;

const json = (body: unknown) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });

/** The defined-by-default answers, matched with `url.includes`. */
const DEFAULTS: Array<[string, () => Response]> = [
  ["/api/shelves", () => json([])],
  ["/api/item-types", () => json([])],
  ["/attachments", () => json({ attachments: [] })],
];

export function mockApi(router: ApiHandler, options: { fallback?: unknown } = {}) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const routed = await router(input, init);
      if (routed !== undefined) return routed;
      const url = String(input);
      for (const [needle, answer] of DEFAULTS) {
        if (url.includes(needle)) return answer();
      }
      if (options.fallback !== undefined) return json(options.fallback);
      throw new Error(`mockApi: no route answered ${url}`);
    });
}
