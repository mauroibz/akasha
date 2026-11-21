import {
  focusManager,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "@/lib/queryClient";

function Probe({ fetcher }: { fetcher: () => Promise<string> }) {
  const query = useQuery({ queryKey: ["probe"], queryFn: fetcher });
  return <p>{query.data ?? "loading"}</p>;
}

afterEach(() => {
  focusManager.setFocused(undefined);
  vi.restoreAllMocks();
});

describe("createQueryClient", () => {
  it("does not refetch every loaded page when the window regains focus", async () => {
    const client = createQueryClient();
    const fetcher = vi.fn(async () => "fresh");
    render(
      <QueryClientProvider client={client}>
        <Probe fetcher={fetcher} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("fresh")).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(1);

    // Long after the data went stale, the window loses and regains focus.
    const later = Date.now() + 10 * 60_000;
    vi.spyOn(Date, "now").mockReturnValue(later);
    act(() => focusManager.setFocused(false));
    act(() => focusManager.setFocused(true));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("keeps data briefly fresh, and still refetches what a write invalidates", async () => {
    const client = createQueryClient();
    let value = "before";
    const fetcher = vi.fn(async () => value);
    const view = render(
      <QueryClientProvider client={client}>
        <Probe fetcher={fetcher} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("before")).toBeInTheDocument();

    // Leaving a screen and coming straight back does not ask again.
    view.unmount();
    render(
      <QueryClientProvider client={client}>
        <Probe fetcher={fetcher} />
      </QueryClientProvider>,
    );
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(fetcher).toHaveBeenCalledTimes(1);

    value = "after";
    await act(() => client.invalidateQueries({ queryKey: ["probe"] }));
    expect(await screen.findByText("after")).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
