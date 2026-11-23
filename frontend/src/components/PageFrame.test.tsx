import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageFrame } from "@/components/PageFrame";

describe("PageFrame", () => {
  it("is the page's main landmark at one of the named widths", () => {
    render(
      <PageFrame width="reading" aria-label="Settings">
        <p>inside</p>
      </PageFrame>,
    );
    const main = screen.getByRole("main", { name: "Settings" });
    expect(main).toHaveAttribute("data-width", "reading");
    expect(main).toHaveTextContent("inside");
  });

  it("keeps a page's own spacing beside the width", () => {
    render(
      <PageFrame width="wide" className="pb-24">
        x
      </PageFrame>,
    );
    const main = screen.getByRole("main");
    expect(main.className).toContain("pb-24");
    expect(main).toHaveAttribute("data-width", "wide");
  });
});
