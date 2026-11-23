import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ModuleLayout } from "@/api/home";

import { AddDialog, PersonalizeBar } from "./Personalize";
import { fullHome, renderWithRouter, types } from "./testHome";

afterEach(() => vi.restoreAllMocks());

type Row = ModuleLayout & { label?: string | null };
const layout: Row[] = [
  { module: "now", size: "L", hidden: false },
  { module: "lately", size: "L", hidden: true },
  { module: "next", size: "L", hidden: false },
  { module: "question", size: "S", hidden: true },
  { module: "shelf:7", size: "M", hidden: true, label: "Shelf: Horror" },
];

function serve() {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      urls.push(String(input));
      return new Response(JSON.stringify(fullHome()));
    }),
  );
  return urls;
}

describe("AddDialog (Sprint 150, DEC-195)", () => {
  it("lists what is not placed, by kind, and previews the chosen one before adding it", async () => {
    const urls = serve();
    const onAdd = vi.fn();
    const onOpenChange = vi.fn();
    renderWithRouter(
      <AddDialog
        open
        onOpenChange={onOpenChange}
        layout={layout}
        types={types}
        onAdd={onAdd}
      />,
    );
    const list = await screen.findByRole("radiogroup", { name: "What to add" });
    expect(
      within(list)
        .getAllByRole("radio")
        .map((radio) => radio.textContent),
    ).toEqual(["Lately", "One question", "Horror"]);
    // The first is chosen and drawn by the component that would stand on the page.
    const preview = screen.getByRole("region", { name: "Preview of Lately" });
    expect(await within(preview).findByText("Pálido fuego")).toBeVisible();
    expect(
      urls.some((url) => url.startsWith("/api/home/preview?module=lately")),
    ).toBe(true);
    // A band has no size to choose.
    expect(screen.queryByRole("group", { name: "Size" })).toBeNull();
    expect(onAdd).not.toHaveBeenCalled();

    await userEvent.click(
      within(list).getByRole("radio", { name: "One question" }),
    );
    await screen.findByRole("region", { name: "Preview of One question" });
    await userEvent.click(
      within(screen.getByRole("group", { name: "Size" })).getByRole("button", {
        name: "Large",
      }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Add One question" }),
    );
    expect(onAdd).toHaveBeenCalledWith("question", "L");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("says so when everything is placed", () => {
    serve();
    renderWithRouter(
      <AddDialog
        open
        onOpenChange={vi.fn()}
        layout={layout.map((row) => ({ ...row, hidden: false }))}
        types={types}
        onAdd={vi.fn()}
      />,
    );
    expect(
      screen.getByText("Everything there is to show is already placed."),
    ).toBeVisible();
  });
});

describe("PersonalizeBar (Sprint 150, DEC-195)", () => {
  it("holds what belongs to the whole front, the media and the theme as dialogs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              chosen: true,
              media: [
                {
                  item_type: "book",
                  label: "Books",
                  presence: "front",
                  held: true,
                },
              ],
            }),
          ),
      ),
    );
    const onReset = vi.fn();
    const onDone = vi.fn();
    renderWithRouter(
      <PersonalizeBar onReset={onReset} onDone={onDone} announcement="" />,
    );
    const bar = screen.getByRole("toolbar", { name: "Personalize" });
    await userEvent.click(within(bar).getByRole("button", { name: "Theme" }));
    const theme = await screen.findByRole("dialog", { name: "Theme" });
    expect(within(theme).getByRole("radio", { name: "Moss" })).toBeVisible();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await userEvent.click(
      within(bar).getByRole("button", { name: "Your media" }),
    );
    const media = await screen.findByRole("dialog", { name: "Your media" });
    expect(
      await within(media).findByRole("radiogroup", { name: "Books are" }),
    ).toBeVisible();
    await userEvent.keyboard("{Escape}");

    await userEvent.click(within(bar).getByRole("button", { name: "Reset" }));
    await userEvent.click(within(bar).getByRole("button", { name: "Done" }));
    expect(onReset).toHaveBeenCalledOnce();
    expect(onDone).toHaveBeenCalledOnce();
  });
});
