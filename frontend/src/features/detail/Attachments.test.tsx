import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { formatBytes } from "@/lib/bytes";
import { findToast } from "@/test/toast";

import { Attachments } from "./Attachments";

const listed = {
  attachments: [
    {
      id: 1,
      filename: "Rayuela.epub",
      byte_size: 2_621_440,
      sha256: "a".repeat(64),
      created_at: "2026-08-14T00:00:00Z",
    },
  ],
};

function renderPanel() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <Attachments itemId={3} />
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("Attachments", () => {
  it("lists each file with its name and a readable size", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(listed)),
    );

    renderPanel();

    const link = await screen.findByRole("link", { name: "Rayuela.epub" });
    expect(link).toHaveAttribute("href", "/api/items/3/attachments/1");
    expect(screen.getByText("2.5 MB")).toBeVisible();
  });

  it("says so plainly when nothing is attached", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ attachments: [] })),
    );

    renderPanel();

    expect(await screen.findByText("No files attached yet.")).toBeVisible();
  });

  it("surfaces the server's own reason when a file is over the cap", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "POST")
        return new Response(
          JSON.stringify({
            error: { code: "attachment_too_large", message: "too big" },
          }),
          { status: 413 },
        );
      return new Response(JSON.stringify({ attachments: [] }));
    });
    renderPanel();
    await screen.findByText("No files attached yet.");

    await userEvent.setup().upload(
      screen.getByLabelText("Attach a file"),
      new File(["x".repeat(64)], "huge.epub", {
        type: "application/epub+zip",
      }),
    );

    expect(
      await findToast(/larger than the limit for attachments/i),
    ).toBeTruthy();
  });

  it("uploads a chosen file and shows it in the list", async () => {
    let uploaded = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "POST") {
        uploaded = true;
        return new Response(JSON.stringify(listed.attachments[0]), {
          status: 201,
        });
      }
      return new Response(
        JSON.stringify(uploaded ? listed : { attachments: [] }),
      );
    });
    renderPanel();
    await screen.findByText("No files attached yet.");

    await userEvent
      .setup()
      .upload(
        screen.getByLabelText("Attach a file"),
        new File(["epub"], "Rayuela.epub", { type: "application/epub+zip" }),
      );

    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Rayuela.epub" })).toBeVisible(),
    );
  });

  it("removes a file when asked", async () => {
    let removed = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "DELETE") {
        removed = true;
        return new Response(null, { status: 204 });
      }
      return new Response(
        JSON.stringify(removed ? { attachments: [] } : listed),
      );
    });
    renderPanel();
    await screen.findByRole("link", { name: "Rayuela.epub" });

    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Remove Rayuela.epub" }));

    expect(await screen.findByText("No files attached yet.")).toBeVisible();
  });

  it("does not take the page down when the list cannot be read", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("nope", { status: 500 }),
    );

    renderPanel();

    expect(await screen.findByText("Files could not be loaded.")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Files" })).toBeVisible();
  });
});

describe("formatBytes", () => {
  it.each([
    [512, "512 B"],
    [1024, "1.0 KB"],
    [2_621_440, "2.5 MB"],
    [15 * 1024 * 1024, "15 MB"],
  ])("renders %i as %s", (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected);
  });
});
