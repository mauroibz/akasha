import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RefileDialog } from "./RefileDialog";

const types = [
  { id: "series", label: "Series", statuses: [], fields: [] },
  { id: "anime", label: "Anime", statuses: [], fields: [] },
];

const candidate = {
  source: "anilist",
  source_id: "1",
  source_refs: [{ source: "anilist", source_id: "1" }],
  title: "Cowboy Bebop",
  subtitle: null,
  creators: [],
  credit: null,
  year: 1998,
  cover_url: null,
  identifiers: {},
  language: null,
  metadata: {},
};

afterEach(() => vi.restoreAllMocks());

describe("RefileDialog", () => {
  it("searches the chosen library and moves the entry to the record confirmed", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        if (url === "/api/item-types")
          return new Response(JSON.stringify(types));
        if (url.startsWith("/api/search?"))
          return new Response(JSON.stringify([candidate]));
        if (url === "/api/entries/7/refile")
          return new Response(JSON.stringify({ id: 12 }));
        return new Response("[]");
      });
    const onMoved = vi.fn();
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RefileDialog
          open
          onOpenChange={vi.fn()}
          entryId={7}
          title="Cowboy Bebop"
          itemType="series"
          onMoved={onMoved}
        />
      </QueryClientProvider>,
    );

    const library = await screen.findByRole("combobox", { name: "Move to" });
    expect(
      await screen.findByRole("option", { name: "Anime" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Series" }),
    ).not.toBeInTheDocument();
    expect(library).toHaveValue("anime");

    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/search?q=Cowboy%20Bebop&type=anime",
      expect.anything(),
    );
    await user.click(
      await screen.findByRole("radio", { name: /Cowboy Bebop.*1998/ }),
    );
    await user.click(screen.getByRole("button", { name: "Move to Anime" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/entries/7/refile",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          source: "anilist",
          source_id: "1",
          source_refs: candidate.source_refs,
        }),
      }),
    );
    await vi.waitFor(() => expect(onMoved).toHaveBeenCalledWith({ id: 12 }));
  });
});
