import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  AUTH_REQUIRED_EVENT,
  readApiError,
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

describe("readApiError", () => {
  function envelope(status: number, error: Record<string, unknown>) {
    return new Response(JSON.stringify({ error }), {
      status,
      headers: { "X-Request-Id": "req-12345678" },
    });
  }

  it("reads the envelope, preferring the sentence written for a person", async () => {
    const error = await readApiError(
      envelope(422, {
        code: "invalid_import_source",
        message: "manifest malformed",
        user_message:
          "Akasha could not read what your browser offered to send.",
        action: "Choose the folder again.",
        details: { field: "manifest" },
      }),
      "fallback",
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe(
      "Akasha could not read what your browser offered to send.",
    );
    expect(error.code).toBe("invalid_import_source");
    expect(error.status).toBe(422);
    expect(error.action).toBe("Choose the folder again.");
    expect(error.details).toEqual({ field: "manifest" });
    expect(error.requestId).toBe("req-12345678");
  });

  it("falls back on the message and code it was given for a body that is not the envelope", async () => {
    const error = await readApiError(
      new Response("<html>bad gateway</html>", { status: 502 }),
      "The file could not be attached",
      "attach_failed",
    );
    expect(error.message).toBe("The file could not be attached");
    expect(error.code).toBe("attach_failed");
    expect(error.status).toBe(502);
    expect(error.action).toBeNull();
    expect(error.details).toEqual({});
    expect(error.requestId).toBeNull();
  });
});
