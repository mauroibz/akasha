import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SegmentedControl } from "@/components/SegmentedControl";

/**
 * The one segmented-control idiom (proposal §3.3), extracted from the library's
 * grid/table toggle and insights' sort toggle — both `flex rounded-full bg-surface
 * p-1` around `aria-pressed` buttons, one of which never got the 44px target the
 * other did (finding 10).
 */
describe("SegmentedControl", () => {
  it("keeps aria-pressed semantics and reports the selected option", () => {
    render(
      <SegmentedControl
        ariaLabel="Library view"
        value="grid"
        onChange={() => undefined}
        options={[
          { value: "grid", label: "Grid", ariaLabel: "Grid view" },
          { value: "table", label: "Table", ariaLabel: "Table view" },
        ]}
      />,
    );
    expect(
      screen.getByRole("group", { name: "Library view" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Grid view" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      screen.getByRole("button", { name: "Table view" }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("gives every option at least a 44px target", () => {
    render(
      <SegmentedControl
        ariaLabel="Sort by"
        value="count"
        onChange={() => undefined}
        options={[
          { value: "count", label: "Most collected" },
          { value: "score", label: "Best rated" },
        ]}
      />,
    );
    for (const button of screen.getAllByRole("button")) {
      expect(button.className).toMatch(/min-h-11/);
    }
  });

  it("calls back with the pressed option's value", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SegmentedControl
        ariaLabel="Sort by"
        value="count"
        onChange={onChange}
        options={[
          { value: "count", label: "Most collected" },
          { value: "score", label: "Best rated" },
        ]}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Best rated" }));
    expect(onChange).toHaveBeenCalledWith("score");
  });
});
