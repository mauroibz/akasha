import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LibraryEntry, LibraryPage } from "@/api/library";
import * as library from "@/api/library";

import { usePatchEntry } from "./usePatchEntry";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

afterEach(() => vi.restoreAllMocks());

const entry = {
  id: 7,
  score: 5,
  status: "read",
  score_provisional: true,
} as unknown as LibraryEntry;

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const key = ["library", { sort: "added" }] as const;
  client.setQueryData(key, {
    pages: [{ items: [entry] } as unknown as LibraryPage],
    pageParams: [undefined],
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const read = () =>
    (client.getQueryData(key) as { pages: LibraryPage[] }).pages[0].items[0];
  return { client, key, wrapper, read };
}

describe("usePatchEntry", () => {
  it("shows the change at once and keeps it when the server agrees", async () => {
    const { key, wrapper, read } = setup();
    vi.spyOn(library, "patchEntry").mockResolvedValue({ ...entry, score: 9 });
    const onSaved = vi.fn();
    const { result } = renderHook(() => usePatchEntry({ key, onSaved }), {
      wrapper,
    });

    act(() => result.current.mutate({ entry, changes: { score: 9 } }));
    await waitFor(() => expect(read().score).toBe(9));
    expect(read().score_provisional).toBe(false);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("restores the previous value and names the row when the save fails", async () => {
    const { key, wrapper, read } = setup();
    vi.spyOn(library, "patchEntry").mockRejectedValue(new Error("offline"));
    const onRollback = vi.fn();
    const { result } = renderHook(() => usePatchEntry({ key, onRollback }), {
      wrapper,
    });

    act(() => result.current.mutate({ entry, changes: { score: 9 } }));
    await waitFor(() => expect(onRollback).toHaveBeenCalledWith(entry));
    expect(read().score).toBe(5);
    expect(read().score_provisional).toBe(true);
  });
});
