import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./HomePage";
import { emptyHome, fullHome, renderWithRouter, types } from "./testHome";

afterEach(() => vi.restoreAllMocks());

function serve(home: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/home")) return new Response(JSON.stringify(home));
      if (url.includes("/api/item-types"))
        return new Response(JSON.stringify(types));
      return new Response("[]");
    }),
  );
}

describe("HomePage", () => {
  it("lays out every module from the one payload", async () => {
    serve(fullHome());
    renderWithRouter(<HomePage />);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      /Day 32 of/,
    );
    for (const name of ["On now", "Up next", "2026", "Your libraries"]) {
      expect(screen.getByRole("region", { name })).toBeVisible();
    }
  });

  it("welcomes an empty library instead of drawing empty modules", async () => {
    serve(emptyHome());
    renderWithRouter(<HomePage />);
    expect(
      await screen.findByRole("heading", { name: "Your desk is ready" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Add something" })).toHaveAttribute(
      "href",
      "/add",
    );
    expect(
      screen.getByRole("link", { name: "Import a library" }),
    ).toHaveAttribute("href", "/import");
    expect(screen.queryByRole("region", { name: "On now" })).toBeNull();
  });

  it("says so when Home cannot be loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 500 })),
    );
    renderWithRouter(<HomePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Home could not be loaded/,
    );
  });
});
