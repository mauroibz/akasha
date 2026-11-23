import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OnNow } from "./OnNow";
import { reading, renderWithRouter, types, watching } from "./testHome";

afterEach(() => vi.restoreAllMocks());

function patches(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "PATCH")
    .map(([url, init]) => [
      String(url),
      JSON.parse(String((init as RequestInit).body)),
    ]);
}

function stubFetch() {
  const fetchMock = vi.fn(
    async (_url: string | URL | Request, init?: RequestInit) =>
      new Response(
        JSON.stringify({
          ...reading,
          ...(init?.body ? JSON.parse(String(init.body)) : {}),
        }),
        { status: 200 },
      ),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("OnNow", () => {
  it("shows fewer entries beneath the first at a smaller size", () => {
    const more = [2, 3, 4].map((id) => ({
      ...watching,
      id: id + 50,
      item: { ...watching.item, title: `Show ${id}` },
    }));
    renderWithRouter(
      <OnNow entries={[reading, watching, ...more]} types={types} size="S" />,
    );
    expect(screen.getByText("Frieren")).toBeVisible();
    expect(screen.queryByText("Show 2")).toBeNull();
    expect(screen.getByText("And 3 more under way.")).toBeVisible();
  });

  it("shows each entry under way with how far through it is", () => {
    renderWithRouter(<OnNow entries={[reading, watching]} types={types} />);
    expect(
      screen.getByRole("heading", {
        name: "Designing Data-Intensive Applications",
      }),
    ).toBeVisible();
    expect(screen.getByText("120 / 600 pages")).toBeVisible();
    expect(screen.getByText("Frieren")).toBeVisible();
  });

  it("logs progress where the domain counts it", async () => {
    const fetchMock = stubFetch();
    renderWithRouter(<OnNow entries={[reading]} types={types} />);
    await userEvent.click(
      screen.getByRole("button", {
        name: "Add 10 pages to Designing Data-Intensive Applications",
      }),
    );
    await waitFor(() =>
      expect(patches(fetchMock)).toEqual([
        ["/api/entries/1", { progress: 130 }],
      ]),
    );
  });

  it("sets an entry aside onto its pile", async () => {
    const fetchMock = stubFetch();
    renderWithRouter(<OnNow entries={[watching]} types={types} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Set Frieren aside" }),
    );
    await waitFor(() =>
      expect(patches(fetchMock)).toEqual([
        ["/api/entries/2", { status: "plan_to_watch" }],
      ]),
    );
  });

  it("opens the finish sheet and finishes from it", async () => {
    const fetchMock = stubFetch();
    renderWithRouter(<OnNow entries={[watching]} types={types} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Mark Frieren as completed" }),
    );
    const sheet = await screen.findByRole("dialog");
    expect(sheet).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: /^Finish/ }));
    await waitFor(() => {
      const [call] = patches(fetchMock);
      expect(call[0]).toBe("/api/entries/2");
      expect(call[1].status).toBe("completed");
    });
  });

  it("says nothing is under way rather than drawing an empty box", () => {
    renderWithRouter(<OnNow entries={[]} types={types} />);
    expect(screen.getByText(/Nothing under way/)).toBeVisible();
  });
});
