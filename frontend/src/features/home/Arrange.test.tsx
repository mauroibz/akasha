import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { ModuleLayout } from "@/api/home";

import { ArrangeControls } from "./Arrange";
import { movedAmongShown, useArrange } from "./useArrange";

type Row = ModuleLayout & { label?: string | null };

const start: Row[] = [
  { module: "next", size: "L", hidden: false },
  { module: "year:book", size: "M", hidden: false, label: "Books this year" },
  { module: "question", size: "S", hidden: true },
  { module: "suggested", size: "M", hidden: false },
  { module: "shelf:7", size: "M", hidden: true, label: "Shelf: Horror" },
  {
    module: "insight:book:scores",
    size: "S",
    hidden: true,
    label: "How you rate books",
  },
];

function Harness({ onChange }: { onChange: (next: ModuleLayout[]) => void }) {
  const [layout, setLayout] = useState<ModuleLayout[]>(start);
  const arrange = useArrange(layout, (next) => {
    setLayout(next);
    onChange(next);
  });
  return (
    <>
      <ul aria-label="Placed">
        {arrange.shown
          .filter((row) => !row.hidden)
          .map((row) => (
            <li key={row.module} data-module={row.module}>
              <ArrangeControls row={row} arrange={arrange} />
            </li>
          ))}
      </ul>
      <button type="button" onClick={() => arrange.add("shelf:7", "L")}>
        add the shelf, large
      </button>
      <p role="status">{arrange.announcement}</p>
    </>
  );
}

const placed = () =>
  within(screen.getByRole("list", { name: "Placed" }))
    .getAllByRole("listitem")
    .map((item) => item.getAttribute("data-module"));

describe("arranging the Library (Sprint 142, DEC-193)", () => {
  it("moves a showcase among those shown with the arrow keys, keeping the focus", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const user = userEvent.setup();
    screen.getByRole("button", { name: "Move More like this" }).focus();
    await user.keyboard("{ArrowLeft}");
    expect(placed()).toEqual(["next", "suggested", "year:book"]);
    expect(
      screen.getByRole("button", { name: "Move More like this" }),
    ).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent(
      "More like this moved to 2 of 3",
    );
    // What is hidden keeps its place in the stored order.
    const saved = onChange.mock.lastCall![0] as ModuleLayout[];
    expect(saved.map((row) => row.module)).toEqual([
      "next",
      "suggested",
      "year:book",
      "question",
      "shelf:7",
      "insight:book:scores",
    ]);
    await user.keyboard("{ArrowUp}{ArrowDown}{ArrowRight}");
    expect(placed()).toEqual(["next", "year:book", "suggested"]);
  });

  it("moves twice for two presses before the stored layout comes back", async () => {
    const onChange = vi.fn();
    function Slow() {
      // The parent never renders the change back.
      const arrange = useArrange(start, onChange);
      return <ArrangeControls row={start[3]} arrange={arrange} />;
    }
    render(<Slow />);
    screen.getByRole("button", { name: "Move More like this" }).focus();
    await userEvent.setup().keyboard("{ArrowLeft}{ArrowLeft}");
    const last = onChange.mock.lastCall![0] as ModuleLayout[];
    expect(last.filter((row) => !row.hidden).map((row) => row.module)).toEqual([
      "suggested",
      "next",
      "year:book",
    ]);
  });

  it("changes a showcase's size", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const group = screen.getByRole("group", { name: "Size of Up next" });
    await userEvent.click(within(group).getByRole("button", { name: "Small" }));
    expect(
      within(group).getByRole("button", { name: "Small" }),
    ).toHaveAttribute("aria-pressed", "true");
    const saved = onChange.mock.lastCall![0] as ModuleLayout[];
    expect(saved.find((row) => row.module === "next")?.size).toBe("S");
  });

  it("removes a thing, and adds one after those shown at the size asked", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Remove Up next" }));
    expect(placed()).toEqual(["year:book", "suggested"]);
    expect(screen.getByRole("status")).toHaveTextContent("Up next removed");

    await user.click(
      screen.getByRole("button", { name: "add the shelf, large" }),
    );
    expect(placed()).toEqual(["year:book", "suggested", "shelf:7"]);
    const saved = onChange.mock.lastCall![0] as ModuleLayout[];
    expect(saved.find((row) => row.module === "shelf:7")).toMatchObject({
      hidden: false,
      size: "L",
    });
    expect(
      screen.getByRole("button", { name: "Move Shelf: Horror" }),
    ).toHaveFocus();
  });

  it("gives a band no size: it is always the whole row", () => {
    function Band() {
      const arrange = useArrange(
        [{ module: "lately", size: "L", hidden: false }],
        vi.fn(),
      );
      return (
        <ArrangeControls
          row={{ module: "lately", size: "L", hidden: false }}
          arrange={arrange}
        />
      );
    }
    render(<Band />);
    expect(screen.getByRole("button", { name: "Remove Lately" })).toBeVisible();
    expect(screen.queryByRole("group", { name: "Size of Lately" })).toBeNull();
  });
});

describe("movedAmongShown", () => {
  it("puts a showcase last among those shown, before nothing hidden moves", () => {
    expect(movedAmongShown(start, "next", 2).map((row) => row.module)).toEqual([
      "year:book",
      "question",
      "suggested",
      "next",
      "shelf:7",
      "insight:book:scores",
    ]);
  });
});
