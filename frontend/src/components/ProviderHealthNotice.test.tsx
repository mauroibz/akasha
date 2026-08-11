import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProviderHealthNotice } from "@/components/ProviderHealthNotice";

function renderNotice() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ProviderHealthNotice />
    </QueryClientProvider>,
  );
}

function stub(body: unknown, status = 200) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), { status }),
  );
}

afterEach(() => vi.restoreAllMocks());

describe("ProviderHealthNotice", () => {
  it("names the unavailable provider and why", async () => {
    stub({
      degraded: true,
      providers: [
        { name: "openlibrary", available: true, reason: null },
        { name: "googlebooks", available: false, reason: "no API key" },
      ],
    });
    renderNotice();
    const notice = await screen.findByRole("status");
    expect(notice).toHaveTextContent(/fewer providers/i);
    expect(notice).toHaveTextContent("googlebooks is unavailable: no API key");
    // A working provider is not reported as broken.
    expect(notice).not.toHaveTextContent(/openlibrary/);
  });

  it("says nothing while every provider is available", async () => {
    stub({
      degraded: false,
      providers: [{ name: "openlibrary", available: true, reason: null }],
    });
    renderNotice();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("stays silent when provider health itself cannot be read", async () => {
    // The notice must never be the reason a search page breaks.
    stub({ error: "boom" }, 500);
    renderNotice();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
