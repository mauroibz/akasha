import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ImportInputSpec } from "@/api/imports";
import { ExportPicker } from "./ExportPicker";

const epubSpec: ImportInputSpec = {
  kind: "export",
  label: "EPUB files",
  field: "files",
  accept: ".epub",
  placeholder: null,
  help: null,
  guide: [],
  empty_state: "Drop .epub files here.",
  help_url: null,
  browsable: false,
  incremental: false,
  accepts_files: true,
  max_bytes: null,
  max_files: 100,
  alternates: [],
};

/**
 * A flat set of files, read from the connector's declaration (Sprint 086): the
 * picker knows nothing about Calibre or EPUBs, only what the spec accepts.
 */
describe("ExportPicker", () => {
  it("accepts what the declaration accepts and is named for its connector", () => {
    render(
      <ExportPicker
        importerId="epub"
        spec={epubSpec}
        inputId="epub-source"
        files={[]}
        onFiles={() => undefined}
      />,
    );
    expect(screen.getByTestId("epub-export-drop-zone")).toBeVisible();
    const input = screen.getByLabelText("EPUB files");
    expect(input).toHaveAttribute("accept", ".epub");
    expect(input).toHaveAttribute("multiple");
    expect(screen.getByText("Drop .epub files here.")).toBeVisible();
  });

  it("names a chosen file the declaration does not accept", () => {
    render(
      <ExportPicker
        importerId="epub"
        spec={epubSpec}
        inputId="epub-source"
        files={[new File(["a"], "Book.EPUB"), new File(["b"], "notes.pdf")]}
        onFiles={() => undefined}
      />,
    );
    expect(screen.getByText(/2 files selected/i)).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent(
      "This file isn't one EPUB files accepts: notes.pdf.",
    );
  });

  it("hands every chosen file over at once", async () => {
    const onFiles = vi.fn();
    render(
      <ExportPicker
        importerId="epub"
        spec={epubSpec}
        inputId="epub-source"
        files={[]}
        onFiles={onFiles}
      />,
    );
    const books = [new File(["a"], "a.epub"), new File(["b"], "b.epub")];
    await userEvent.upload(screen.getByLabelText("EPUB files"), books);
    expect(onFiles).toHaveBeenCalledWith(books);
  });
});
