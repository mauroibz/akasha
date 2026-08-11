import { act, render, screen } from "@testing-library/react";
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

  it("marks a provisional score distinctly from the score ramp", () => {
    const { rerender } = render(
      <ScorePicker value={6} provisional onChange={() => {}} />,
    );
    const provisional = screen.getByRole("button", { name: /6/i });
    expect(provisional).toHaveAttribute("data-provisional", "true");
    // Provisional is a border treatment, not a colour: amber already means
    // "score 4-6" on the DEC-026 ramp and cannot also mean "imported guess".
    expect(provisional.className).toContain("border-dashed");
    rerender(<ScorePicker value={6} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /6/i })).toHaveAttribute(
      "data-provisional",
      "false",
    );
  });

  it("colours the trigger and segments by the DEC-026 score ramp", async () => {
    const user = userEvent.setup();
    render(<ScorePicker value={2} onChange={() => {}} />);
    const trigger = screen.getByRole("button", { name: /score: 2/i });
    expect(trigger.className).toContain("text-score-low");
    await user.click(trigger);
    expect(screen.getByRole("button", { name: "Score 2" }).className).toContain(
      "bg-score-low",
    );
    expect(
      screen.getByRole("button", { name: "Score 10" }).className,
    ).toContain("bg-surface-raised");
  });

  it("previews the ramp on hover without committing a score", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    // Compact mode, because that is where the trigger and the panel coexist:
    // the full-size picker replaces its trigger with the panel while open.
    render(<ScorePicker value={2} onChange={onChange} compact />);
    const trigger = screen.getByRole("button", { name: /score: 2/i });
    await user.click(trigger);
    // Sweeping the segments recolours the trigger live, so the ramp is legible
    // before the commit rather than only after it.
    await user.hover(screen.getByRole("button", { name: "Score 9" }));
    expect(trigger.className).toContain("text-score-top");
    expect(screen.getByRole("button", { name: "Score 9" }).className).toContain(
      "bg-score-top",
    );
    expect(onChange).not.toHaveBeenCalled();
    await user.unhover(screen.getByRole("button", { name: "Score 9" }));
    expect(trigger.className).toContain("text-score-low");
    expect(trigger.textContent).toContain("2");
  });

  it("previews on keyboard focus too, so the ramp is not pointer-only", async () => {
    const user = userEvent.setup();
    render(<ScorePicker value={1} onChange={() => {}} compact />);
    const trigger = screen.getByRole("button", { name: /score: 1/i });
    await user.click(trigger);
    await act(async () =>
      screen.getByRole("button", { name: "Score 7" }).focus(),
    );
    expect(trigger.className).toContain("text-score-high");
  });

  it("previews the fill in the full-size picker, which has no visible trigger", async () => {
    const user = userEvent.setup();
    render(<ScorePicker value={2} onChange={() => {}} />);
    await user.click(screen.getByRole("button", { name: /score: 2/i }));
    await user.hover(screen.getByRole("button", { name: "Score 8" }));
    expect(screen.getByRole("button", { name: "Score 8" }).className).toContain(
      "bg-score-high",
    );
    expect(screen.getByRole("button", { name: "Score 3" }).className).toContain(
      "bg-score-high/25",
    );
  });

  it("commits once and closes in the same tick", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ScorePicker value={4} onChange={onChange} compact />);
    await user.click(screen.getByRole("button", { name: /score: 4/i }));
    await user.click(screen.getByRole("button", { name: "Score 10" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(10);
    // The panel disappearing is the confirmation that the commit landed; it is
    // deliberately not deferred behind an exit animation.
    expect(
      screen.queryByRole("button", { name: "Score 10" }),
    ).not.toBeInTheDocument();
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
