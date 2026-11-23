import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ItemType } from "@/api/library";
import type { Media, MediumChoice } from "@/api/media";

import { inTheirOrder } from "./useMedia";
import { YourMedia } from "./YourMedia";

afterEach(() => vi.restoreAllMocks());

const media: Media = {
  chosen: false,
  media: [
    { item_type: "book", label: "Books", presence: "front", held: true },
    { item_type: "album", label: "Albums", presence: "front", held: true },
    { item_type: "anime", label: "Anime", presence: "off", held: false },
  ],
};

function serve() {
  const puts: MediumChoice[][] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "PUT") {
        const body = JSON.parse(String(init.body)) as { media: MediumChoice[] };
        puts.push(body.media);
        return new Response(
          JSON.stringify({
            chosen: true,
            media: body.media.map((row) => ({
              ...row,
              label: media.media.find((m) => m.item_type === row.item_type)!
                .label,
              held: row.item_type !== "anime",
            })),
          }),
        );
      }
      return new Response(JSON.stringify(media));
    }),
  );
  return puts;
}

function renderControl() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <YourMedia />
    </QueryClientProvider>,
  );
}

const order = () =>
  screen
    .getAllByRole("listitem")
    .map((item) => item.getAttribute("data-medium"));

describe("YourMedia (Sprint 143, DEC-193)", () => {
  it("lists the media in the person's order, each with what it is to them", async () => {
    serve();
    renderControl();
    await screen.findByRole("region", { name: "Your media" });
    expect(order()).toEqual(["book", "album", "anime"]);
    expect(
      within(screen.getByRole("radiogroup", { name: "Anime are" })).getByRole(
        "radio",
        { name: "Off" },
      ),
    ).toBeChecked();
    expect(screen.getByText("nothing yet")).toBeVisible();
  });

  it("moves a medium earlier and stores the whole order at once", async () => {
    const puts = serve();
    renderControl();
    await userEvent.click(
      await screen.findByRole("button", { name: "Move Anime earlier" }),
    );
    expect(order()).toEqual(["book", "anime", "album"]);
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]).toEqual([
      { item_type: "book", presence: "front" },
      { item_type: "anime", presence: "off" },
      { item_type: "album", presence: "front" },
    ]);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Anime moved to 2 of 3",
    );
    expect(
      screen.getByRole("button", { name: "Move Books earlier" }),
    ).toBeDisabled();
  });

  it("turns a medium off, and says so", async () => {
    const puts = serve();
    renderControl();
    const albums = await screen.findByRole("radiogroup", {
      name: "Albums are",
    });
    await userEvent.click(within(albums).getByRole("radio", { name: "Off" }));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0][1]).toEqual({ item_type: "album", presence: "off" });
    expect(screen.getByRole("status")).toHaveTextContent("Albums off");
  });
});

describe("inTheirOrder", () => {
  const types = ["book", "album", "anime", "movie"].map(
    (id) => ({ id, label: id }) as ItemType,
  );

  it("orders the registry as the person does and leaves out what is off", () => {
    const chosen: Media = {
      chosen: true,
      media: [
        { item_type: "anime", label: "Anime", presence: "front", held: true },
        { item_type: "book", label: "Books", presence: "kept", held: true },
        { item_type: "album", label: "Albums", presence: "off", held: true },
      ],
    };
    // A medium the list does not name keeps its place after those it does.
    expect(inTheirOrder(types, chosen).map((type) => type.id)).toEqual([
      "anime",
      "book",
      "movie",
    ]);
  });

  it("is the registry as declared when there is no usable answer", () => {
    expect(inTheirOrder(types, undefined)).toEqual(types);
    expect(inTheirOrder(types, {} as Media)).toEqual(types);
    expect(inTheirOrder(types, { chosen: true, media: [] })).toEqual(types);
  });
});
