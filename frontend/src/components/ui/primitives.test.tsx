import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./empty-state";
import { FilePicker } from "./file-picker";
import { NativeSelect } from "./native-select";
import { Loading } from "./skeleton";

describe("FilePicker", () => {
  it("keeps the caller's label on the real input and names what was chosen", async () => {
    const onChange = vi.fn();
    render(
      <label>
        Your list
        <FilePicker accept=".csv" onChange={onChange} />
      </label>,
    );
    const input = screen.getByLabelText(/your list/i, { selector: "input" });
    expect(input).toHaveAttribute("type", "file");
    expect(screen.getByText("No file chosen yet")).toBeInTheDocument();
    await userEvent.upload(
      input,
      new File(["a,b"], "libros.csv", { type: "text/csv" }),
    );
    expect(onChange).toHaveBeenCalledOnce();
    expect(screen.getByText("libros.csv")).toBeInTheDocument();
  });

  it("opens the platform picker from the drawn button", async () => {
    render(<FilePicker aria-label="Cover" buttonLabel="Replace cover" />);
    const input = screen.getByLabelText("Cover") as HTMLInputElement;
    const click = vi.spyOn(input, "click");
    await userEvent.click(screen.getByText("Replace cover"));
    expect(click).toHaveBeenCalled();
  });
});

describe("NativeSelect", () => {
  it("is still a select the keyboard and tests can drive", async () => {
    const onChange = vi.fn();
    render(
      <NativeSelect aria-label="Separator" defaultValue="" onChange={onChange}>
        <option value="">Auto</option>
        <option value=";">Semicolon</option>
      </NativeSelect>,
    );
    await userEvent.selectOptions(screen.getByLabelText("Separator"), ";");
    expect(onChange).toHaveBeenCalled();
  });
});

describe("Loading and EmptyState", () => {
  it("says the loading sentence once, as a status", () => {
    render(<Loading label="Loading detail…" shape="detail" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading detail…");
  });

  it("offers the next step", () => {
    render(
      <EmptyState
        title="Nothing on this shelf yet"
        action={<button>Find something</button>}
      />,
    );
    expect(screen.getByText("Nothing on this shelf yet")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Find something" }),
    ).toBeInTheDocument();
  });
});
