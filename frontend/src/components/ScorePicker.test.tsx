import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ScorePicker } from "@/components/ScorePicker";

afterEach(() => vi.restoreAllMocks());

describe("ScorePicker", () => {
  it("shows the current score and opens a segmented 1-10 picker on click", async () => {
    const user = userEvent.setup();
    let score = 7;
    render(
      <ScorePicker
        value={score}
        onChange={(v) => (score = v ?? 0)}
        label="Score for Rayuela"
      />,
    );
    expect(
      screen.getByRole("button", { name: /score for rayuela: 7/i }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /score for rayuela: 7/i }),
    );
    // 10 segment buttons visible
    for (const n of [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) {
      expect(screen.getByRole("button", { name: `Score ${n}` })).toBeVisible();
    }
    // Click 9
    await user.click(screen.getByRole("button", { name: "Score 9" }));
    expect(score).toBe(9);
  });

  it("shows provisional styling with a dot indicator", () => {
    render(<ScorePicker value={6} provisional onChange={() => {}} />);
    const button = screen.getByRole("button", { name: /6/i });
    expect(button.className).toContain("amber");
  });

  it("clears the score via the clear button", async () => {
    const user = userEvent.setup();
    let score: number | null = 5;
    render(<ScorePicker value={score} onChange={(v) => (score = v)} />);
    await user.click(screen.getByRole("button", { name: /score: 5/i }));
    await user.click(screen.getByRole("button", { name: /clear score/i }));
    expect(score).toBeNull();
  });

  it("closes on Escape without changing the score", async () => {
    const user = userEvent.setup();
    let score = 8;
    render(<ScorePicker value={score} onChange={(v) => (score = v ?? 0)} />);
    await user.click(screen.getByRole("button", { name: /score: 8/i }));
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("button", { name: "Score 5" }),
    ).not.toBeInTheDocument();
    expect(score).toBe(8);
  });

  it("closes on outside click", async () => {
    const user = userEvent.setup();
    let score = 3;
    render(
      <div>
        <ScorePicker value={score} onChange={(v) => (score = v ?? 0)} />
        <button>Outside</button>
      </div>,
    );
    await user.click(screen.getByRole("button", { name: /score: 3/i }));
    expect(screen.getByRole("button", { name: "Score 5" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Outside" }));
    expect(
      screen.queryByRole("button", { name: "Score 5" }),
    ).not.toBeInTheDocument();
  });
});
