import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { HomePage } from "./HomePage";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <HomePage />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("announces loading and then ready health", async () => {
  let resolveResponse: ((response: Response) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveResponse = resolve;
        }),
    ),
  );
  renderPage();
  expect(screen.getByRole("status")).toHaveTextContent("Checking your library");
  resolveResponse?.(
    new Response(JSON.stringify({ status: "ready" }), { status: 200 }),
  );
  expect(await screen.findByText("Akasha is ready.")).toBeVisible();
});

test("announces unavailable health", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("", { status: 503 })),
  );
  renderPage();
  expect(await screen.findByText(/Akasha is unavailable/)).toBeVisible();
});
