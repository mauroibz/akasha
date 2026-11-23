import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { ModuleLayout } from "@/api/home";

import { EditHome } from "./EditHome";
import { fallbackLayout } from "./layout";

function Harness({
  onChange,
  initial = fallbackLayout,
}: {
  onChange: (next: ModuleLayout[]) => void;
  initial?: ModuleLayout[];
}) {
  const [layout, setLayout] = useState(initial);
  return (
    <EditHome
      open
      onOpenChange={() => undefined}
      layout={layout}
      defaults={fallbackLayout}
      onChange={(next) => {
        setLayout(next);
        onChange(next);
      }}
    />
  );
}

const order = () =>
  within(screen.getByRole("list", { name: "Modules" }))
    .getAllByRole("listitem")
    .map((item) => item.getAttribute("data-module"));

describe("EditHome", () => {
  it("lists every module in the layout's order", () => {
    render(<Harness onChange={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: "Edit home" })).toBeVisible();
    expect(order()).toEqual(fallbackLayout.map((row) => row.module));
  });

  it("moves a module with the arrow keys on its handle", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const user = userEvent.setup();
    screen.getByRole("button", { name: "Move Lately" }).focus();
    await user.keyboard("{ArrowUp}");
    expect(order().slice(0, 4)).toEqual(["now", "next", "lately", "year"]);
    expect(onChange).toHaveBeenLastCalledWith(
      expect.arrayContaining([expect.objectContaining({ module: "lately" })]),
    );
    expect(screen.getByRole("button", { name: "Move Lately" })).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Lately moved to 3 of 10",
    );
    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(order().slice(2, 5)).toEqual(["year", "libraries", "lately"]);
  });

  it("moves twice for two presses before the stored layout comes back", async () => {
    const onChange = vi.fn();
    // The parent has not rendered the first move back when the second key lands.
    render(
      <EditHome
        open
        onOpenChange={() => undefined}
        layout={fallbackLayout}
        defaults={fallbackLayout}
        onChange={onChange}
      />,
    );
    screen.getByRole("button", { name: "Move Lately" }).focus();
    await userEvent.setup().keyboard("{ArrowUp}{ArrowUp}");
    const last = onChange.mock.lastCall![0] as ModuleLayout[];
    expect(last.map((row) => row.module).slice(0, 3)).toEqual([
      "now",
      "lately",
      "next",
    ]);
  });

  it("changes a module's size", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const row = screen.getByRole("group", { name: "Size of Tidy up" });
    await userEvent
      .setup()
      .click(within(row).getByRole("button", { name: "Large" }));
    expect(within(row).getByRole("button", { name: "Large" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const saved = onChange.mock.lastCall![0] as ModuleLayout[];
    expect(saved.find((m) => m.module === "tidy")?.size).toBe("L");
  });

  it("hides a module with its switch", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const toggle = screen.getByRole("switch", { name: "Show Lent out" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    await userEvent.setup().click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    const saved = onChange.mock.lastCall![0] as ModuleLayout[];
    expect(saved.find((m) => m.module === "lent")?.hidden).toBe(true);
  });

  it("puts the default back with Reset", async () => {
    const onChange = vi.fn();
    const reversed = [...fallbackLayout].reverse();
    render(<Harness onChange={onChange} initial={reversed} />);
    expect(order()[0]).toBe("suggested");
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Reset" }));
    expect(order()).toEqual(fallbackLayout.map((row) => row.module));
    expect(onChange).toHaveBeenLastCalledWith(fallbackLayout);
  });

  it("offers the library tiles no size: they take the whole row", () => {
    render(<Harness onChange={vi.fn()} />);
    expect(
      screen.queryByRole("group", { name: "Size of Library tiles" }),
    ).toBeNull();
    expect(
      within(screen.getByRole("list", { name: "Modules" }))
        .getAllByRole("listitem")
        .find((item) => item.getAttribute("data-module") === "libraries"),
    ).toHaveTextContent("Full width");
  });
});
