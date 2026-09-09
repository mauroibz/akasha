import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AUTH_REQUIRED_EVENT,
  request,
  SetupRequired,
  Unauthenticated,
} from "./request";

afterEach(() => vi.restoreAllMocks());

describe("request", () => {
  it("raises Unauthenticated and announces a 401 once", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                code: "unauthenticated",
                message: "Authentication is required",
                details: {},
              },
            }),
            { status: 401 },
          ),
      ),
    );
    const listener = vi.fn();
    window.addEventListener(AUTH_REQUIRED_EVENT, listener);

    await expect(request("/api/entries")).rejects.toBeInstanceOf(
      Unauthenticated,
    );
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(AUTH_REQUIRED_EVENT, listener);
  });

  it("raises SetupRequired only for a setup_required 409", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                code: "setup_required",
                message: "Create the first admin",
                details: {},
              },
            }),
            { status: 409 },
          ),
      ),
    );

    await expect(request("/api/entries")).rejects.toBeInstanceOf(SetupRequired);
  });

  it("returns ordinary responses unchanged and forwards fetch options", async () => {
    const response = new Response("conflict", { status: 409 });
    const fetchMock = vi.fn(async () => response);
    vi.stubGlobal("fetch", fetchMock);
    const signal = new AbortController().signal;

    await expect(
      request("/api/entries", { method: "POST", signal }),
    ).resolves.toBe(response);
    expect(fetchMock).toHaveBeenCalledWith("/api/entries", {
      method: "POST",
      signal,
    });
  });
});
