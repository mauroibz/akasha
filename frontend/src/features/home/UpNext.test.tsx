import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UpNext } from "./UpNext";
import { entry, fullHome, renderWithRouter, types } from "./testHome";

afterEach(() => vi.restoreAllMocks());

describe("UpNext", () => {
  it("shows three picks small and five large", () => {
    const picks = Array.from({ length: 5 }, (_, index) => ({
      entry: entry(60 + index, `Pick ${index}`, "book", { status: "to_read" }),
      score: 0,
      reasons: [],
    }));
    const { unmount } = renderWithRouter(
      <UpNext picks={picks} pile={41} types={types} size="S" />,
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    unmount();
    renderWithRouter(<UpNext picks={picks} pile={41} types={types} size="L" />);
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
  });

  it("lists the pile in order, each with its strongest reason under it", () => {
    const home = fullHome();
    renderWithRouter(<UpNext picks={home.next} pile={41} types={types} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Mistborn");
    expect(items[0]).toHaveTextContent("Next in Mistborn; you gave book 1 a 9");
    // One reason a pick: the strongest, not every signal that fired.
    expect(items[0]).not.toHaveTextContent("Waiting since");
    expect(items[1]).toHaveTextContent("Mushishi");
    expect(items[1]).toHaveTextContent("Waiting since Sep 2025");
  });

  it("starts an entry by moving it to its domain's under-way status", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(fullHome().next[1].entry)),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithRouter(
      <UpNext picks={fullHome().next} pile={41} types={types} />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Start Mushishi" }),
    );
    await waitFor(() => {
      const [url, init] = fetchMock.mock.calls[0] as unknown as [
        string,
        RequestInit,
      ];
      expect(url).toBe("/api/entries/11");
      expect(init.method).toBe("PATCH");
      expect(JSON.parse(String(init.body))).toEqual({ status: "watching" });
    });
  });

  it("offers the finish sheet where the domain has nothing to be under way in", async () => {
    const film = {
      entry: entry(12, "Paris, Texas", "movie", { status: "watchlist" }),
      score: 0.3,
      reasons: [{ signal: "waiting" as const, text: "Waiting since Jan 2025" }],
    };
    renderWithRouter(<UpNext picks={[film]} pile={1} types={types} />);
    expect(
      screen.queryByRole("button", { name: "Start Paris, Texas" }),
    ).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Mark Paris, Texas as watched" }),
    );
    expect(await screen.findByRole("dialog")).toHaveTextContent(
      "You finished Paris, Texas",
    );
  });

  it("says the pile is empty rather than drawing an empty box", () => {
    renderWithRouter(<UpNext picks={[]} pile={0} types={types} />);
    expect(screen.getByText(/Nothing waiting/)).toBeVisible();
  });
});
