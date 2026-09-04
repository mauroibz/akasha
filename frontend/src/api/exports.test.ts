import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadExport, exportViewUrl, getExports } from "./exports";
import { ImportRequestError } from "./imports";
import type { ExportViewDefinition } from "./exports";

afterEach(() => {
  vi.restoreAllMocks();
});

const tableView: ExportViewDefinition = {
  id: "table",
  label: "Table (Books)",
  item_types: ["book"],
  media_type: "text/csv; charset=utf-8",
  lossless: false,
  guide: ["Open this file in any spreadsheet application."],
  help_url: null,
  carries: ["Title", "Creator", "Year"],
  count: 3,
};

describe("getExports", () => {
  it("returns whatever the registry declares, invented views included", async () => {
    const invented: ExportViewDefinition = {
      id: "letterboxd",
      label: "Letterboxd",
      item_types: ["movie"],
      media_type: "text/csv; charset=utf-8",
      lossless: false,
      guide: ["Upload at letterboxd.com/import."],
      help_url: "https://letterboxd.com/import/",
      carries: ["title", "watched date", "rating"],
      count: 12,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([tableView, invented])),
    );
    await expect(getExports()).resolves.toEqual([tableView, invented]);
  });

  it("raises the standard error envelope on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "boom", user_message: "The registry is unavailable." },
        }),
        { status: 500 },
      ),
    );
    await expect(getExports()).rejects.toThrow("The registry is unavailable.");
  });
});

describe("exportViewUrl", () => {
  it("names the view and the domain, both encoded", () => {
    expect(exportViewUrl(tableView, "book")).toBe(
      "/api/export/table?type=book",
    );
  });
});

describe("downloadExport", () => {
  it("hands the browser a same-named file on success", async () => {
    const bytes = "Title,Creator\r\nFicciones,Borges\r\n";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(bytes, {
        headers: {
          "Content-Disposition": 'attachment; filename="akasha-book-table.csv"',
        },
      }),
    );
    const clicked: string[] = [];
    const anchor = document.createElement("a");
    const clickSpy = vi
      .spyOn(anchor, "click")
      .mockImplementation(() => clicked.push(anchor.download));
    vi.spyOn(document, "createElement").mockReturnValue(anchor);
    // jsdom does not implement either: Node.js has no notion of a blob URL.
    URL.createObjectURL = vi.fn().mockReturnValue("blob:mock");
    URL.revokeObjectURL = vi.fn();
    const revoke = URL.revokeObjectURL;

    await downloadExport("/api/export/table?type=book");

    expect(clicked).toEqual(["akasha-book-table.csv"]);
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(revoke).toHaveBeenCalledWith("blob:mock");
  });

  it("raises the standard error envelope rather than downloading a failure body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "export_view_not_found",
            message: "No export view named 'nonsense'",
          },
        }),
        { status: 404 },
      ),
    );
    await expect(
      downloadExport("/api/export/nonsense?type=book"),
    ).rejects.toThrow(ImportRequestError);
  });
});
