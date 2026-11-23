import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UpNext } from "./UpNext";
import { entry, fullHome, renderWithRouter, types } from "./testHome";

afterEach(() => vi.restoreAllMocks());

describe("UpNext", () => {
  it("lists the pile in order, each with why it is there", () => {
    const home = fullHome();
    renderWithRouter(<UpNext picks={home.next} pile={41} types={types} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Mistborn");
    expect(items[0]).toHaveTextContent("Brandon Sanderson averages 8.5");
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
      reason: "waiting" as const,
      since: "2025-01-01",
    };
    renderWithRouter(<UpNext picks={[film]} pile={1} types={types} />);
    expect(
      screen.queryByRole("button", { name: "Start Paris, Texas" }),
    ).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Finished Paris, Texas" }),
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
